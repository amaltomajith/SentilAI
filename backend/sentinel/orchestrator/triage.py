"""Honest triage. Deterministic rules first; the LLM only breaks ties; no LLM => 'uncertain' (never engage)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sentinel.grounding import extract_candidates

CATS = {
    "payment": r"\b(pay|send|transfer|deposit|remit|credit)\b.{0,40}(₹|rs\.?|rupees?|inr|\d{3,})|(₹|rs\.?)\s?\d",
    "urgency": r"\b(urgent|immediately|right now|within \d+|last (warning|chance)|final warning|hurry|expires?|today only)\b",
    "threat": r"\b(blocked?|suspend(ed)?|arrest|police|cbi|legal action|warrant|freeze|frozen|seiz|fir\b|court case|disconnect)",
    "lure": r"\b(lottery|lucky draw|you (have )?won|prize|refund|cashback|kyc|reward points|guaranteed returns?|double your|work from home|registration fee)\b",
    "credential": r"\b(otp|cvv|pin|password|card number|anydesk|teamviewer|quick ?support|screen ?share)\b",
}
BENIGN = [
    r"no action (is )?required", r"will be delivered", r"out for delivery", r"order #?\w*\d+",
    r"if (this was )?not (done )?by you,? call", r"debited from a/?c", r"credited to your a/?c",
    r"are we (still )?meeting", r"let me know if", r"see you (at|on|tomorrow)", r"^\s*(hi|hello|hey|good (morning|evening))\b[\w\s,.!]{0,40}$",
]
_C = {k: re.compile(v, re.IGNORECASE) for k, v in CATS.items()}
_B = [re.compile(p, re.IGNORECASE) for p in BENIGN]


@dataclass
class TriageResult:
    verdict: str  # scam | benign | uncertain
    confidence: int
    reasons: list[str] = field(default_factory=list)
    source: str = "rules"  # rules | llm | none


def rule_triage(text: str) -> TriageResult:
    cats = [k for k, p in _C.items() if p.search(text)]
    iocs = {c.kind for c in extract_candidates(text)}
    payment_rail = bool(iocs & {"upi", "bank_account", "ifsc"})
    phishing_link = "url" in iocs and bool(set(cats) & {"urgency", "threat", "lure"})
    score = len(cats) + (2 if payment_rail else 0) + (1 if phishing_link else 0)
    reasons = cats + sorted(iocs)
    if score >= 3 or (payment_rail and "payment" in cats) or ("credential" in cats and score >= 2):
        return TriageResult("scam", min(99, 60 + 10 * score), reasons)
    benign_hit = any(p.search(text) for p in _B)
    if score == 0 and benign_hit:
        return TriageResult("benign", 85, ["benign_pattern"])
    if score <= 1 and benign_hit and not payment_rail:
        return TriageResult("benign", 75, ["benign_pattern"] + reasons)
    return TriageResult("uncertain", 50, reasons)


TRIAGE_PROMPT = ('Classify the SMS/WhatsApp message. Reply with ONLY JSON {"verdict":"scam"|"benign","confidence":0-100}. '
                 "scam = tries to obtain money, credentials, OTPs or clicks via fear/urgency/lures. "
                 "benign = genuine notification or normal personal chat. If truly unsure choose benign.")


async def triage(text: str, llm=None) -> TriageResult:
    r = rule_triage(text)
    if r.verdict != "uncertain" or llm is None:
        return r
    try:
        import json
        raw = await llm.complete(TRIAGE_PROMPT, [{"role": "user", "content": text}], purpose="triage", max_tokens=40, temperature=0.0)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        v = data.get("verdict")
        if v in ("scam", "benign"):
            return TriageResult(v, int(data.get("confidence", 60)), r.reasons + ["llm"], "llm")
    except Exception:
        pass
    return TriageResult("uncertain", 50, r.reasons + ["llm_unavailable"], "none")