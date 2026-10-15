"""Reads the scammer's message and the session state; decides scam type, stage, pressure and reply language.

Rules only (no extra model call: it costs nothing and is auditable). The model still only writes text; this module and the bandit decide
WHICH tactic the text should carry out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SCAM_TYPES: dict[str, re.Pattern] = {k: re.compile(v, re.I) for k, v in {
    "police_impersonation": r"\b(cbi|police|arrest|customs|narcotics|court|digital arrest|trai|ed officer|money laundering|fedex)\b",
    "kyc_bank": r"\b(kyc|account (is |will be )?(blocked|suspended|freez\w*|closed)|net ?banking|debit card|credit card|pan card|sbi|hdfc|icici|axis bank)\b",
    "upi_cashback": r"\b(cashback|refund|reward points?|scan (the )?qr|collect request|phonepe|paytm|google pay|gpay)\b",
    "job_task": r"\b(work from home|part[- ]time|earn rs|per day|registration fee|typing job|like (and )?subscribe|task)\b",
    "lottery_prize": r"\b(lottery|lucky draw|you (have )?won|prize|winner|kbc|processing fee)\b",
    "investment_crypto": r"\b(invest\w*|bitcoin|crypto|guaranteed returns?|trading|stock tips?|double your)\b",
    "sextortion": r"\b(private video|nude|blackmail|send (it )?to your contacts|leak)\b",
    "delivery_parcel": r"\b(parcel|courier|package|custom duty|address update|delivery (failed|attempt))\b",
    "electricity_bill": r"\b(electricity|power cut|bill (is )?(due|overdue)|disconnect\w*)\b",
    "tech_support": r"\b(anydesk|teamviewer|remote access|virus|microsoft support|your computer)\b",
    "loan": r"\b(pre-?approved loan|instant loan|emi|low interest)\b",
}.items()}
_URGENCY = re.compile(r"\b(urgent\w*|immediately|last warning|final notice|right now|within \d+ ?(hours?|hrs?|minutes?|mins?)|today only|arrest\w*|blocked|legal action|suspend\w*|jail|fir)\b", re.I)

_SCRIPTS = (
    ("Hindi", "\u0900", "\u097f"), ("Bengali", "\u0980", "\u09ff"), ("Punjabi", "\u0a00", "\u0a7f"), ("Gujarati", "\u0a80", "\u0aff"),
    ("Tamil", "\u0b80", "\u0bff"), ("Telugu", "\u0c00", "\u0c7f"), ("Kannada", "\u0c80", "\u0cff"), ("Malayalam", "\u0d00", "\u0d7f"),
    ("Urdu", "\u0600", "\u06ff"),
)
_HINGLISH = re.compile(r"\b(kya|hai|hain|nahi|nahin|karo|kijiye|kijiyega|aap|aapka|apka|bhai|bhejo|batao|abhi|turant|jaldi|paisa|khata|band|ho jayega|samajh)\b", re.I)


@dataclass(frozen=True)
class Analysis:
    scam_type: str
    stage: str          # opening | hook | payment_pushed | threat
    pressure: str       # low | medium | high
    language: str       # English | Hinglish | Hindi | Tamil | ...


def detect_language(text: str) -> str:
    for name, lo, hi in _SCRIPTS:
        if sum(lo <= ch <= hi for ch in text) >= 3:
            return name
    if len(_HINGLISH.findall(text)) >= 2:
        return "Hinglish"
    return "English"


def lang_instruction(detected: str, user_languages: list[str] | None) -> str:
    """Mirror the scammer's language only if the user actually speaks it; otherwise English."""
    ok = {x.lower() for x in (user_languages or [])}
    if detected == "Hinglish" and ok & {"hinglish", "hindi"}:
        return "Reply in Hinglish (Hindi written in English letters), the way the other person writes."
    if detected == "Hindi" and "hindi" in ok:
        return "Reply in Hindi (Devanagari script), the way the other person writes."
    if detected not in ("English", "Hinglish", "Hindi") and detected.lower() in ok:
        return f"Reply in {detected}, the way the other person writes."
    return "Reply in simple English."


def analyze(text: str, exchange_count: int, captured_kinds: set[str]) -> Analysis:
    best, best_n = "other", 0
    for name, pat in SCAM_TYPES.items():
        n = len(pat.findall(text))
        if n > best_n:
            best, best_n = name, n
    hits = len(_URGENCY.findall(text))
    pressure = "high" if hits >= 3 else "medium" if hits >= 1 else "low"
    if exchange_count == 0:
        stage = "opening"
    elif captured_kinds & {"upi", "bank_account"}:
        stage = "payment_pushed"
    elif pressure == "high":
        stage = "threat"
    else:
        stage = "hook"
    return Analysis(best, stage, pressure, detect_language(text))