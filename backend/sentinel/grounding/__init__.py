"""The ONE IOC extractor + literal-substring verifier.

Rule: an artifact is scammer intelligence only if its exact text literally appears in the scammer's
inbound message AND it is not a Sentinel-generated honey token. Models never get to "propose" IOCs.

Grounding v2 (SENTINEL_GROUNDING_V2=1, OFF by default) fixes failures measured in eval/reports/ioc.md:
  * toll-free numbers (1800/1860...) and numbers labelled as a reference, UTR, transaction, order, tracking, invoice, PNR,
    URN, FIR, case, complaint, card, Aadhaar or OTP are not bank accounts (they had become fake "payment rails" in triage);
  * an 11-digit 0-prefixed mobile is a phone, not an account;
  * links without a scheme (www.x.in, x-y.com/path) are URLs, for a fixed list of top-level domains;
  * "name @ psp" with spaces around @ is a UPI id when psp is a known UPI handle;
  * Indic digits are read as the same digits (stored in ASCII);
  * obfuscated forms are read deterministically: "name at psp" / "name(at)psp" / "name[at]psp" (known UPI handles only;
    the bare word "at" also needs a payment word before it), defanged links (hxxp://, [.], (.), [dot], and " . " after a
    scheme), IFSC codes in lower case or with a space after "IFSC", and phones written 987.654.3210.
The literal rule stays: an IOC is kept only if the text contains it, read through a fixed, documented set of rewrites
(Indic digits, digit grouping, the "at"/"dot" spellings above, IFSC letter case). The rewrites are code, not a model, and
look-alike letters still never match.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from sentinel.config import get_settings

URL_RE = re.compile(r"https?://[^\s<>\"'{}|\\^`\[\]]+", re.IGNORECASE)
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
UPI_RE = re.compile(r"(?<![\w.%+-])[A-Za-z0-9][A-Za-z0-9._-]{1,}@[A-Za-z][A-Za-z0-9]{1,}(?![\w-]*\.[A-Za-z])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
DIGITS_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?\d[\d\s-]{7,20}\d(?!\d)")
ACCOUNT_HINT = re.compile(r"(a/?c|acc(?:oun)?t|acct|bank)\W{0,12}(?:no|number|num|#)?\W{0,6}$", re.IGNORECASE)

# ---- v2 only ----
_LABEL_TAIL = r"\b\W{0,12}(?:no|number|num|id|#)?\W{0,6}$"
# a number labelled like this is neither a phone nor an account (it is a reference, order, card, Aadhaar or OTP number)
NOT_IOC_HINT = re.compile(r"\b(ref(?:erence)?|utr|txn|transaction|order|tracking|invoice|pnr|urn|card|aadhaa?r|otp)" + _LABEL_TAIL,
                          re.IGNORECASE)
# a number labelled like this is not an account, but may still be a phone ("case officer id 9xxxxxxxxx" is ambiguous)
NOT_ACCOUNT_HINT = re.compile(r"\b(id|case|complaint|fir)" + _LABEL_TAIL, re.IGNORECASE)
TLDS = ("com|in|net|org|info|co|io|xyz|top|online|site|live|link|app|shop|club|icu|vip|cc|me|biz|tk|ml|ga|cf|gq|buzz|"
        "website|store|click|example|invalid")
BARE_URL_RE = re.compile(r"(?<![\w@./:-])(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + TLDS + r")\b"
                         r"(?![.@-]?\w)(?:/[^\s<>\"'{}|\\^`\[\]]*)?", re.IGNORECASE)
UPI_PSPS = {"ybl", "ibl", "axl", "upi", "paytm", "apl", "okaxis", "oksbi", "okhdfcbank", "okicici", "icici", "sbi", "hdfcbank",
            "axisbank", "kotak", "yesbank", "freecharge", "airtel", "jio", "waaxis", "wahdfcbank", "wasbi", "waicici", "pthdfc",
            "ptsbi", "ptaxis", "ptyes", "idfcbank", "indus", "fbl", "rbl", "barodampay", "unionbank", "pnb", "cnrb", "boi"}
UPI_SPACED_RE = re.compile(r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._-]{1,})(?:\s+@\s*|\s*@\s+)([A-Za-z][A-Za-z0-9]{1,})\b(?![\w-]*\.[A-Za-z])")
TOLL_FREE = ("1800", "1860")
DOT_OBF = r"(?:\[\.\]|\(\.\)|\{\.\}|\[dot\]|\(dot\)|\s\.\s)"
OBF_URL_RE = re.compile(r"(?<![\w@/-])(?:(?P<scheme>h(?:xx|tt)ps?)(?::\/\/|\[:\]\/\/|\[:\/\/\]))?"
                        r"(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:" + DOT_OBF + r"|\.))+(?:" + TLDS + r"))\b"
                        r"(?P<path>/[^\s<>\"'{}|\\^`\[\]]*)?", re.IGNORECASE)
UPI_AT_RE = re.compile(r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._-]{1,})\s*(?:\(at\)|\[at\]|\{at\})\s*([A-Za-z][A-Za-z0-9]{1,})\b",
                       re.IGNORECASE)
UPI_ATWORD_RE = re.compile(r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._-]{1,})\s+at\s+([A-Za-z][A-Za-z0-9]{1,})\b"
                           r"(?!\s+(?:branch|atm|office|colony|bank|counter|cent(?:re|er)|building|tower|mall|station))", re.IGNORECASE)
PAY_WORD = re.compile(r"\b(upi|vpa|gpay|google\s*pay|phone\s*pe|phonepe|paytm|bhim|pay|send|transfer|id)\b", re.IGNORECASE)
AT_STOP = {"am", "is", "are", "was", "be", "me", "us", "him", "her", "them", "you", "i", "we", "here", "there", "home", "office",
           "meet", "wait", "waiting", "stay", "staying", "reached", "come", "see", "look", "it", "this", "that", "now", "money",
           "account", "acct", "cash", "amount", "fee", "fees", "rs", "rupees", "bank", "upi", "balance", "payment", "pay", "send",
           "transfer", "deposit", "bill", "rent", "card", "loan", "salary", "id"}
# with the bare word "at", bank names people write in plain English ("my account at SBI") are not read as UPI handles
ATWORD_PSPS = UPI_PSPS - {"sbi", "icici", "kotak", "pnb", "boi", "axisbank", "hdfcbank", "yesbank", "airtel", "jio", "indus", "rbl",
                          "unionbank", "cnrb", "idfcbank", "barodampay"}
IFSC_LOOSE_RE = re.compile(r"\b([A-Za-z]{4})\s?(0[A-Za-z0-9]{6})\b")
IFSC_CONTEXT = re.compile(r"\bifsc\b", re.IGNORECASE)          # the word IFSC within 24 characters before
PHONE_DOT_RE = re.compile(r"(?<![\d.])([6-9]\d{2})\.(\d{3})\.(\d{4})(?!\d)(?!\.\d)")

KINDS = ("upi", "phone", "url", "bank_account", "ifsc")
_V2_DEFAULT = get_settings().grounding_v2


def use_v2(enabled: bool) -> None:
    """Set the process-wide default (evaluation scripts and tests). Production reads SENTINEL_GROUNDING_V2 at start-up."""
    global _V2_DEFAULT
    _V2_DEFAULT = bool(enabled)


def v2_enabled() -> bool:
    return _V2_DEFAULT


def _ascii_digits(text: str) -> str:
    """Map every Unicode decimal digit to ASCII, one character for one, so positions are unchanged."""
    return "".join(str(unicodedata.digit(c)) if (c.isdigit() and not c.isascii() and unicodedata.digit(c, None) is not None) else c
                   for c in text)


@dataclass(frozen=True)
class Candidate:
    kind: str
    value: str  # exact form for upi/url/ifsc; digits-only for phone/bank_account


@dataclass(frozen=True)
class Grounded:
    candidate: Candidate
    accepted: bool
    reason: str  # ok | not_in_message | honey_token


def extract_candidates(text: str, v2: bool | None = None) -> list[Candidate]:
    v2 = _V2_DEFAULT if v2 is None else v2
    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str):
        if (kind, value) not in seen:
            seen.add((kind, value))
            out.append(Candidate(kind, value))

    url_spans = []
    obf_spans = []
    if v2:
        for m in OBF_URL_RE.finditer(text):
            scheme, host = m.group("scheme") or "", m.group("host")
            defanged = scheme.lower().startswith("hxx") or re.search(DOT_OBF, host, re.IGNORECASE)
            if not defanged or (re.search(r"\s", host) and not scheme) or not re.search(r"[a-z]", host.lower()):
                continue                                    # plain links are handled below; " . " needs a scheme
            clean_host = re.sub(DOT_OBF, ".", host, flags=re.IGNORECASE)
            prefix = ("https://" if scheme.lower().endswith("s") else "http://") if scheme else ""
            obf_spans.append(m.span())
            add("url", (prefix + clean_host + (m.group("path") or "")).rstrip(".,;:!?)\"'"))
    for m in URL_RE.finditer(text):
        url_spans.append(m.span())
        if any(s <= m.start() < e for s, e in obf_spans):
            continue                                        # "http://x . example" is one link, not "http://x"
        add("url", m.group(0).rstrip(".,;:!?)\"'"))
    for m in IFSC_RE.finditer(text):
        add("ifsc", m.group(0))
    email_spans = [m.span() for m in EMAIL_RE.finditer(text)]
    if v2:
        for m in BARE_URL_RE.finditer(text):
            inside = any(s <= m.start() < e for s, e in url_spans + email_spans + obf_spans)
            host = m.group(0).split("/")[0].lower()
            if not inside and re.search(r"[a-z]", host.rsplit(".", 1)[0]):   # "5.in the evening" is not a link
                add("url", m.group(0).rstrip(".,;:!?)\"'"))
    for m in UPI_RE.finditer(text):
        if any(s <= m.start() < e for s, e in email_spans):
            continue
        add("upi", m.group(0))
    if v2:
        for m in UPI_SPACED_RE.finditer(text):
            if m.group(2).lower() in UPI_PSPS and not any(s <= m.start() < e for s, e in email_spans):
                add("upi", f"{m.group(1)}@{m.group(2)}")
        for m in UPI_AT_RE.finditer(text):
            if m.group(2).lower() in UPI_PSPS:
                add("upi", f"{m.group(1)}@{m.group(2)}")
        for m in UPI_ATWORD_RE.finditer(text):
            name, psp = m.group(1), m.group(2)
            if psp.lower() in ATWORD_PSPS and name.lower() not in AT_STOP and re.search(r"[A-Za-z]", name) and PAY_WORD.search(text[max(0, m.start() - 40):m.start()]):
                add("upi", f"{name}@{psp}")
        for m in IFSC_LOOSE_RE.finditer(text):
            value = (m.group(1) + m.group(2)).upper()
            if IFSC_RE.fullmatch(value) and IFSC_CONTEXT.search(text[max(0, m.start() - 24):m.start()]):
                add("ifsc", value)
        for m in PHONE_DOT_RE.finditer(_ascii_digits(text)):
            add("phone", "".join(m.groups()))
    scan = _ascii_digits(text) if v2 else text
    for m in DIGITS_RE.finditer(scan):
        digits = re.sub(r"\D", "", m.group(0))
        has_cc = len(digits) == 12 and digits.startswith("91") and digits[2] in "6789"
        core = digits[2:] if has_cc else digits
        before = scan[max(0, m.start() - 24):m.start()]
        hinted = bool(ACCOUNT_HINT.search(before))
        if v2:
            if digits.startswith(TOLL_FREE) and len(digits) in (10, 11):
                continue                                    # toll-free service numbers are neither phones nor accounts
            if not hinted and NOT_IOC_HINT.search(before):
                continue                                    # labelled reference / order / card / Aadhaar / OTP number
            if not hinted and NOT_ACCOUNT_HINT.search(before):
                if len(core) == 10 and core[0] in "6789":
                    add("phone", core)
                continue
            if len(digits) == 11 and digits[0] == "0" and digits[1] in "6789" and not hinted:
                add("phone", digits[1:])                    # trunk-prefixed mobile (0 98765 43210)
                continue
        if len(core) == 10:
            # mobile numbers start 6-9; a bare 10-digit number is only an account if the text says so
            # (this also keeps toll-free numbers like 1800... out of the IOC list)
            if core[0] in "6789" and not hinted:
                add("phone", core)
            elif hinted:
                add("bank_account", digits)
        elif 9 <= len(digits) <= 18:
            add("bank_account", digits)
    return out


def appears_literally(candidate: Candidate, text: str, v2: bool | None = None) -> bool:
    """Exact substring check. Phone/bank digits tolerate only whitespace/hyphen grouping (98765 43210).
    No case-folding or Unicode normalisation: look-alike characters must NOT match.
    v2 adds the fixed rewrites in `_deobfuscate` (see the module docstring)."""
    v2 = _V2_DEFAULT if v2 is None else v2
    if candidate.kind in ("phone", "bank_account"):
        return candidate.value in re.sub(r"[\s.-]" if v2 else r"[\s-]", "", _ascii_digits(text) if v2 else text)
    if candidate.value in text:
        return True
    if not v2:
        return False
    if candidate.kind == "ifsc":
        return candidate.value in re.sub(r"\s", "", text).upper()
    return candidate.value in _deobfuscate(text)


def _deobfuscate(text: str) -> str:
    """The only rewrites v2 applies before the literal check. ASCII only: look-alike letters are left as they are."""
    t = re.sub(r"\bhxx(ps?)(?::\/\/|\[:\]\/\/|\[:\/\/\])", r"htt\1://", text, flags=re.IGNORECASE)
    t = re.sub(DOT_OBF, ".", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*(?:\(at\)|\[at\]|\{at\})\s*", "@", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+at\s+", "@", t, flags=re.IGNORECASE)
    return re.sub(r"\s*@\s*", "@", t)


def ground(candidates, inbound_text: str, honey_values=frozenset(), v2: bool | None = None) -> list[Grounded]:
    honey = {h.lower() for h in honey_values}
    results: list[Grounded] = []
    for c in candidates:
        host = url_host(c.value) if c.kind == "url" else ""
        if c.value.lower() in honey or (host and host in honey):
            results.append(Grounded(c, False, "honey_token"))
        elif not appears_literally(c, inbound_text, v2):
            results.append(Grounded(c, False, "not_in_message"))
        else:
            results.append(Grounded(c, True, "ok"))
    return results


def url_host(url: str) -> str:
    """Host of a URL value, with or without a scheme (v2 stores scheme-less links as written)."""
    return (urlparse(url if "://" in url else "http://" + url).hostname or "").lower()


def extract_grounded(inbound_text: str, honey_values=frozenset(), v2: bool | None = None) -> list[Candidate]:
    return [g.candidate for g in ground(extract_candidates(inbound_text, v2), inbound_text, honey_values, v2) if g.accepted]


def extract_for_leak_check(text: str) -> list[Candidate]:
    """For the outbound gate: anything that looks like an identifier, in either version. v2's 'not an account' filters
    are about what counts as scammer intelligence; they must never make the leak check looser. Flag off: exactly v1."""
    out = extract_candidates(text, v2=False)
    if _V2_DEFAULT:
        out += [c for c in extract_candidates(text, v2=True) if c not in out]
    return out
