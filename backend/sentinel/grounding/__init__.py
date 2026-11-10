"""The ONE IOC extractor + literal-substring verifier.

Rule: an artifact is scammer intelligence only if its exact text literally appears in the scammer's
inbound message AND it is not a Sentinel-generated honey token. Models never get to "propose" IOCs.

Grounding v2 (SENTINEL_GROUNDING_V2=1, OFF by default) fixes failures measured in eval/reports/ioc.md:
  * toll-free numbers (1800/1860...) and numbers labelled as a reference, UTR, transaction, order, tracking, invoice, PNR,
    URN, FIR, case, complaint, card, Aadhaar or OTP are not bank accounts (they had become fake "payment rails" in triage);
  * an 11-digit 0-prefixed mobile is a phone, not an account;
  * links without a scheme (www.x.in, x-y.com/path) are URLs, for a fixed list of top-level domains;
  * "name @ psp" with spaces around @ is a UPI id when psp is a known UPI handle;
  * Indic digits are read as the same digits (stored in ASCII).
The literal rule stays: v2 only adds two narrow, documented tolerances to `appears_literally` (Indic digit script for
phone/account digits, and whitespace around '@' for UPI ids). Look-alike letters still never match.
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
    for m in URL_RE.finditer(text):
        url_spans.append(m.span())
        add("url", m.group(0).rstrip(".,;:!?)\"'"))
    for m in IFSC_RE.finditer(text):
        add("ifsc", m.group(0))
    email_spans = [m.span() for m in EMAIL_RE.finditer(text)]
    if v2:
        for m in BARE_URL_RE.finditer(text):
            inside = any(s <= m.start() < e for s, e in url_spans + email_spans)
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
    v2 adds: Indic digits count as the same digits; whitespace around '@' is ignored for UPI ids."""
    v2 = _V2_DEFAULT if v2 is None else v2
    if candidate.kind in ("phone", "bank_account"):
        return candidate.value in re.sub(r"[\s-]", "", _ascii_digits(text) if v2 else text)
    if v2 and candidate.kind == "upi" and candidate.value not in text:
        return candidate.value in re.sub(r"\s*@\s*", "@", text)
    return candidate.value in text


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
