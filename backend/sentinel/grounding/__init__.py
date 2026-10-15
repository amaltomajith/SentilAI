"""The ONE IOC extractor + literal-substring verifier.

Rule: an artifact is scammer intelligence only if its exact text literally appears in the scammer's
inbound message AND it is not a Sentinel-generated honey token. Models never get to "propose" IOCs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>\"'{}|\\^`\[\]]+", re.IGNORECASE)
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
UPI_RE = re.compile(r"(?<![\w.%+-])[A-Za-z0-9][A-Za-z0-9._-]{1,}@[A-Za-z][A-Za-z0-9]{1,}(?![\w-]*\.[A-Za-z])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
DIGITS_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?\d[\d\s-]{7,20}\d(?!\d)")
ACCOUNT_HINT = re.compile(r"(a/?c|acc(?:oun)?t|acct|bank)\W{0,12}(?:no|number|num|#)?\W{0,6}$", re.IGNORECASE)

KINDS = ("upi", "phone", "url", "bank_account", "ifsc")


@dataclass(frozen=True)
class Candidate:
    kind: str
    value: str  # exact form for upi/url/ifsc; digits-only for phone/bank_account


@dataclass(frozen=True)
class Grounded:
    candidate: Candidate
    accepted: bool
    reason: str  # ok | not_in_message | honey_token


def extract_candidates(text: str) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str):
        if (kind, value) not in seen:
            seen.add((kind, value))
            out.append(Candidate(kind, value))

    for m in URL_RE.finditer(text):
        add("url", m.group(0).rstrip(".,;:!?)\"'"))
    for m in IFSC_RE.finditer(text):
        add("ifsc", m.group(0))
    email_spans = [m.span() for m in EMAIL_RE.finditer(text)]
    for m in UPI_RE.finditer(text):
        if any(s <= m.start() < e for s, e in email_spans):
            continue
        add("upi", m.group(0))
    for m in DIGITS_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        has_cc = len(digits) == 12 and digits.startswith("91") and digits[2] in "6789"
        core = digits[2:] if has_cc else digits
        hinted = bool(ACCOUNT_HINT.search(text[max(0, m.start() - 24):m.start()]))
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


def appears_literally(candidate: Candidate, text: str) -> bool:
    """Exact substring check. Phone/bank digits tolerate only whitespace/hyphen grouping (98765 43210).
    No case-folding or Unicode normalisation: look-alike characters must NOT match."""
    if candidate.kind in ("phone", "bank_account"):
        return candidate.value in re.sub(r"[\s-]", "", text)
    return candidate.value in text


def ground(candidates, inbound_text: str, honey_values=frozenset()) -> list[Grounded]:
    honey = {h.lower() for h in honey_values}
    results: list[Grounded] = []
    for c in candidates:
        host = (urlparse(c.value).hostname or "").lower() if c.kind == "url" else ""
        if c.value.lower() in honey or (host and host in honey):
            results.append(Grounded(c, False, "honey_token"))
        elif not appears_literally(c, inbound_text):
            results.append(Grounded(c, False, "not_in_message"))
        else:
            results.append(Grounded(c, True, "ok"))
    return results


def extract_grounded(inbound_text: str, honey_values=frozenset()) -> list[Candidate]:
    return [g.candidate for g in ground(extract_candidates(inbound_text), inbound_text, honey_values) if g.accepted]