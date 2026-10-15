"""Deterministic outbound policy gate. The model drafts; this code decides what is allowed to leave.

Checks: AI self-disclosure, prompt-injection / jailbreak compliance, code output, leakage of any
URL/UPI/phone/account/long number that is not on the approved list, and length.
On violation: repair (drop offending sentences / truncate); if still unsafe or too short -> deterministic
stall template. `enabled=False` exists ONLY so tests can run the positive control (prove the attack lands
when the guard is off).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from sentinel.grounding import extract_candidates

MAX_WORDS = 60

SELF_DISCLOSURE = [
    r"\bas an? (ai|artificial|language model|llm|assistant|chatbot)\b",
    r"\bi(?:'m| am) (?:just )?an? (ai|artificial intelligence|language model|llm|chatbot|bot|virtual assistant)\b",
    r"\b(language model|large language model|llm|chatgpt|gpt-?\d|openai|anthropic|claude|llama|groq|sambanova|gemini)\b",
    r"\bi (?:do not|don't|cannot|can't) (?:have|possess) (?:personal )?(?:feelings|a body|emotions)\b",
    r"\bmy (?:system )?(?:prompt|instructions|programming|training)\b",
    r"\bi was (?:trained|programmed|created|built) (?:by|to)\b",
]
INJECTION_COMPLIANCE = [
    r"```",
    r"\b(?:def|class)\s+\w+\s*[\(:]",
    r"^\s*(?:import|from)\s+\w+",
    r"\bprint\s*\(",
    r"<\s*script\b",
    r"\bselect\b.+\bfrom\b",
    r"\bsudo\s+\w+",
    r"\bignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions|rules|prompts?)\b",
    r"\b(?:developer|dan|jailbreak|god) mode\b",
    r"\bi (?:will|shall) now (?:act|behave|respond|pretend) as\b",
    r"\bhere(?:'s| is) (?:the|a|your) (?:python |javascript |sql |bash )?(?:code|script|poem|essay|story|recipe)\b",
    r"\bsystem prompt\b",
    r"\bnew instructions?\b",
]
# What a *scammer message* looks like when it tries to hijack the persona.
INBOUND_INJECTION = [
    r"\bignore (?:all |any |the )?(?:previous|prior|above|earlier|your) (?:instructions|rules|prompts?|programming)\b",
    r"\b(?:you are|act as|pretend (?:to be|you are)|roleplay as) (?:now )?(?:an? )?(?:ai|assistant|chatgpt|dan|developer|hacker|programmer)\b",
    r"\b(?:system prompt|your prompt|your instructions|reveal your)\b",
    r"\bwrite (?:me )?(?:a |an |some )?(?:python|javascript|code|script|program|poem|essay|story|function|sql)\b",
    r"\b(?:are you|r u) (?:an? )?(?:ai|bot|robot|chatgpt|machine|human)\b",
    r"\b(?:developer|jailbreak|dan) mode\b",
    r"\brepeat (?:after me|everything|the above|your)\b",
    r"\btranslate (?:the following|this) (?:into|to)\b",
]

FALLBACKS = [
    "Kindly wait one moment sir, my phone screen is hanging. I am trying again.",
    "Sir, I am an old man and this is taking some time. Please do not be angry, I am trying to pay.",
    "One moment please sir. My son has set up the phone only, I am not understanding this button.",
    "Kindly be patient sir. The app is showing some error, I am checking once more.",
    "Please revert sir, the network is very slow here. I will try again immediately.",
    "Sir, I am ready to pay but the screen is not responding. Kindly give me two minutes.",
]

_S = [re.compile(p, re.IGNORECASE) for p in SELF_DISCLOSURE]
_I = [re.compile(p, re.IGNORECASE | re.MULTILINE | re.DOTALL) for p in INJECTION_COMPLIANCE]
_IN = [re.compile(p, re.IGNORECASE) for p in INBOUND_INJECTION]
_LONGNUM = re.compile(r"\d{6,}")
_SENT = re.compile(r"(?<=[.!?])\s+")


def looks_like_injection(inbound_text: str) -> bool:
    return any(p.search(inbound_text) for p in _IN)


@dataclass
class Violation:
    code: str
    detail: str


@dataclass
class GateResult:
    draft: str
    final: str
    verdict: str  # pass | repaired | fallback | bypassed
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "violations": [v.__dict__ for v in self.violations]}


def _norm(v: str) -> str:
    return re.sub(r"[\s-]", "", v).lower()


def _protected_hits(text: str, protected: set[str] | frozenset[str]) -> bool:
    """True if any protected term (real name, employer, own phone tail, ...) appears in text. Never echoes the term."""
    low = " ".join(text.lower().split())
    digits = re.sub(r"\D", "", text)
    for t in protected:
        if t.isdigit():
            if t in digits:
                return True
        elif re.search(r"(?<![^\W_])" + re.escape(t) + r"(?![^\W_])", low):
            return True
    return False


def detect(text: str, approved: set[str] | frozenset[str] = frozenset(), protected: set[str] | frozenset[str] = frozenset()) -> list[Violation]:
    approved_n = {_norm(a) for a in approved}
    out: list[Violation] = []
    if protected and _protected_hits(text, protected):
        out.append(Violation("real_detail_leak", "a protected personal detail"))
    for p in _S:
        m = p.search(text)
        if m:
            out.append(Violation("self_disclosure", m.group(0)))
    for p in _I:
        m = p.search(text)
        if m:
            out.append(Violation("injection_compliance", m.group(0)[:40]))
    for c in extract_candidates(text):
        if _norm(c.value) not in approved_n:
            out.append(Violation("leak", f"{c.kind}:{c.value}"))
    for m in _LONGNUM.finditer(re.sub(r"[\s-]", "", text)):
        if m.group(0) not in {a for a in approved_n}:
            if not any(m.group(0) in a for a in approved_n):
                out.append(Violation("numeric_leak", m.group(0)[:12]))
    if len(text.split()) > MAX_WORDS:
        out.append(Violation("too_long", f"{len(text.split())} words"))
    if not text.strip():
        out.append(Violation("empty", ""))
    return out


def fallback_for(seed: str) -> str:
    return FALLBACKS[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(FALLBACKS)]


def _truncate(text: str) -> str:
    words, kept = 0, []
    for s in _SENT.split(text.strip()):
        n = len(s.split())
        if words + n > MAX_WORDS:
            break
        kept.append(s)
        words += n
    return " ".join(kept) if kept else " ".join(text.split()[:MAX_WORDS])


def run_gate(draft: str, approved: set[str] | frozenset[str] = frozenset(), *, enabled: bool = True,
             seed: str = "", protected: set[str] | frozenset[str] = frozenset()) -> GateResult:
    if not enabled:
        return GateResult(draft, draft, "bypassed", detect(draft, approved, protected))
    violations = detect(draft, approved, protected)
    if not violations:
        return GateResult(draft, draft.strip(), "pass")
    sentences = [s for s in _SENT.split(draft.strip()) if s]
    kept = [s for s in sentences if not detect(s, approved, protected) or all(v.code == "too_long" for v in detect(s, approved, protected))]
    repaired = _truncate(" ".join(kept)) if kept else ""
    if len(repaired.split()) >= 3 and not detect(repaired, approved, protected):
        return GateResult(draft, repaired, "repaired", violations)
    return GateResult(draft, fallback_for(seed or draft), "fallback", violations)