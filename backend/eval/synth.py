"""Seeded synthetic message generator. Every record it emits has `synthetic: True`.

Committed corpora hold TEMPLATES with placeholders such as {PHONE_1} or {UPI_2|spaced}; realistic-looking values are only
created here, at run time, from a seed, so they never reach git (the repo is public and a random 10-digit number labelled
"scammer" could belong to a real person). Rendered files go to eval/data/ (git-ignored).

Placeholder grammar: {KIND_n} or {KIND_n|format}. The record's "iocs" list names the slots that are true IOCs; every other
slot is a trap that must NOT be extracted (OTP, order number, card number, toll-free number, decoy UPI, ...).

    python -m eval.synth --seed 1 --out eval/data/corpus.jsonl      # handwritten templates + generated messages, rendered
"""
from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

GENERATOR_VERSION = "1"
HERE = Path(__file__).resolve().parent
HANDWRITTEN = HERE / "corpus" / "handwritten.jsonl"
SLOT_RE = re.compile(r"\{([A-Z]+)_(\d+)(?:\|([a-z0-9_+]+))?\}")
DEVANAGARI = str.maketrans("0123456789", "०१२३४५६७८९")
PSPS = ["ybl", "okaxis", "paytm", "oksbi", "okhdfcbank", "ibl", "upi", "axl", "okicici"]
WORDS = ["kyc", "refund", "helpdesk", "officer", "rewards", "verify", "secure", "support", "claim", "update", "care", "desk"]
TLDS = ["example", "invalid"]
IOC_KINDS = ("upi", "phone", "url", "bank_account", "ifsc")
DECOY_HONEY_PREFIX = "synthdecoy."


@dataclass
class Slot:
    kind: str        # PHONE | ACCT | IFSC | UPI | URL | DECOY | OTP | ORDER | CARD | TOLLFREE | AADHAAR | REF
    canonical: str   # value an analyst would record (digits-only for phone/account, lower-case UPI, scheme-less URL)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def new_slot(kind: str, rng: random.Random) -> Slot:
    if kind == "PHONE":
        return Slot(kind, rng.choice("6789") + _digits(rng, 9))
    if kind == "ACCT":
        return Slot(kind, rng.choice("123456789") + _digits(rng, rng.randint(10, 15)))
    if kind == "IFSC":
        return Slot(kind, "SYN" + rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") + "0" + _digits(rng, 6))
    if kind in ("UPI", "DECOY"):
        user = ("synth" if kind == "UPI" else DECOY_HONEY_PREFIX) + rng.choice(WORDS) + rng.choice(["", ".", "_"]) + _digits(rng, rng.randint(0, 3))
        return Slot(kind, f"{user}@{rng.choice(PSPS)}")
    if kind == "URL":
        host = f"{rng.choice(WORDS)}-{rng.choice(WORDS)}{_digits(rng, rng.randint(0, 2))}.{rng.choice(TLDS)}"
        path = rng.choice(["", "/pay", "/kyc", "/login", "/claim?id=" + _digits(rng, 4)])
        return Slot(kind, host + path)
    if kind == "OTP":
        return Slot(kind, _digits(rng, 6))
    if kind == "ORDER":
        return Slot(kind, rng.choice("123456789") + _digits(rng, 12))
    if kind == "CARD":
        return Slot(kind, rng.choice("456") + _digits(rng, 15))
    if kind == "AADHAAR":
        return Slot(kind, rng.choice("23456789") + _digits(rng, 11))
    if kind == "REF":
        return Slot(kind, rng.choice("123456789") + _digits(rng, 11))
    if kind == "TOLLFREE":
        return Slot(kind, "1800" + _digits(rng, 7))
    raise ValueError(f"unknown slot kind {kind}")


def render_value(slot: Slot, fmt: str | None) -> str:
    v, f = slot.canonical, fmt or "plain"
    if slot.kind == "PHONE":
        return {"plain": v, "spaced": f"{v[:5]} {v[5:]}", "dashed": f"{v[:3]}-{v[3:6]}-{v[6:]}", "cc": f"+91{v}", "cc_space": f"+91 {v}",
                "cc_dash": f"+91-{v}", "zero": f"0{v}", "dev": v.translate(DEVANAGARI), "dotted": f"{v[:3]}.{v[3:6]}.{v[6:]}",
                "triple": f"{v[:3]} {v[3:6]} {v[6:]}"}[f]
    if slot.kind in ("UPI", "DECOY"):
        user, psp = v.split("@")
        return {"plain": v, "spaced": f"{user} @ {psp}", "atword": f"{user} at {psp}", "upper": v.upper(), "paren": f"{user}(at){psp}"}[f]
    if slot.kind == "URL":
        host = v.split("/")[0]
        return {"plain": "http://" + v, "https": "https://" + v, "noscheme": v, "www": "www." + v, "defanged": "hxxp://" + v.replace(".", "[.]", 1),
                "spaced_dot": "http://" + host.replace(".", " . ", 1) + v[len(host):]}[f]
    if slot.kind == "ACCT":
        return {"plain": v, "grouped": " ".join(v[i:i + 4] for i in range(0, len(v), 4)), "dev": v.translate(DEVANAGARI)}[f]
    if slot.kind == "IFSC":
        return {"plain": v, "lower": v.lower(), "spaced": f"{v[:4]} {v[4:]}"}[f]
    if slot.kind in ("CARD", "AADHAAR"):
        return {"plain": v, "grouped": " ".join(v[i:i + 4] for i in range(0, len(v), 4))}[f]
    if slot.kind == "TOLLFREE":
        return {"plain": v, "spaced": f"{v[:4]} {v[4:7]} {v[7:]}", "dashed": f"{v[:4]}-{v[4:7]}-{v[7:]}"}[f]
    return v


KIND_OF_SLOT = {"PHONE": "phone", "ACCT": "bank_account", "IFSC": "ifsc", "UPI": "upi", "URL": "url"}


def render(record: dict, rng: random.Random) -> dict:
    """Fill a template record. Returns a rendered record with text, gold IOCs (kind, canonical) and the honey values used."""
    slots: dict[str, Slot] = {}

    def sub(m: re.Match) -> str:
        key = f"{m.group(1)}_{m.group(2)}"
        if key not in slots:
            slots[key] = new_slot(m.group(1), rng)
        return render_value(slots[key], m.group(3))
    text = SLOT_RE.sub(sub, record["text"])
    gold = []
    for key in record.get("iocs", []):
        if key not in slots:
            raise ValueError(f"{record['id']}: ioc slot {key} not in text")
        gold.append({"kind": KIND_OF_SLOT[slots[key].kind], "value": slots[key].canonical})
    honey = [s.canonical for s in slots.values() if s.kind == "DECOY"]
    out = {k: v for k, v in record.items() if k != "text"}
    return out | {"template": record["text"], "text": text, "gold_iocs": gold, "honey": honey, "synthetic": True, "generator_version": GENERATOR_VERSION}


# ---------------- generated messages (template grammar) ----------------
OPENERS = {
    "kyc_bank": ["Dear customer, your SBI account KYC is pending.", "HDFC Bank: your net banking will be blocked today due to incomplete KYC.",
                 "Your debit card is suspended. Update PAN card details now.", "ICICI alert: account will be freezed, KYC not updated."],
    "police_impersonation": ["This is CBI cyber cell. Your Aadhaar is linked to a money laundering case.", "Mumbai police: a FedEx parcel in your name has narcotics.",
                             "You are under digital arrest. Do not disconnect this call.", "Customs department: illegal items found, court case will be filed."],
    "upi_cashback": ["Congrats! You got Rs 2,000 cashback on PhonePe.", "Your refund of Rs 1,499 is ready. Accept the collect request to receive it.",
                     "Google Pay reward points expiring today, claim cashback now.", "Paytm cashback pending. Scan the QR to receive money."],
    "job_task": ["Part time work from home job, earn Rs 3000 per day.", "Simple task: like and subscribe YouTube videos, earn Rs 50 per like.",
                 "Typing job available. Registration fee Rs 499 only.", "Hiring now! Part-time online task, daily payment."],
    "lottery_prize": ["Congratulations! You won Rs 25 lakh in the KBC lucky draw.", "You are the lucky winner of a Tata Safari car prize.",
                      "Your number won the Jio lottery. Pay processing fee to claim.", "Winner! Claim your prize of Rs 10,00,000 today."],
    "investment_crypto": ["Invest Rs 10,000 and get guaranteed returns of 30% weekly.", "Join our crypto trading group, double your money in 7 days.",
                          "Bitcoin investment plan, guaranteed returns, zero risk.", "Expert stock tips daily, invest with us and earn big."],
    "sextortion": ["I have your private video. Pay or I will send it to your contacts.", "Your nude video call is recorded. Pay now or it will leak.",
                   "We will leak your private video to your family unless you pay."],
    "delivery_parcel": ["Your parcel delivery failed. Address update required.", "India Post: package on hold, pay Rs 25 redelivery fee.",
                        "Courier attempt failed. Pay custom duty to release your package."],
    "electricity_bill": ["Dear consumer, electricity bill is overdue. Power cut tonight at 9:30 pm.", "Your electricity connection will be disconnected today.",
                         "MSEB: bill due not updated, power will be disconnected."],
    "tech_support": ["Microsoft support: your computer has a virus. Install AnyDesk for remote access.", "Your computer is hacked. Call our technician now.",
                     "Install TeamViewer so our engineer can fix your bank app."],
    "loan": ["Pre-approved loan of Rs 5 lakh, low interest, instant loan in 10 minutes.", "Instant loan approved. Pay file charge to release the amount.",
             "Low interest personal loan, EMI only Rs 999."],
}
PRESSURE = ["", "Urgent.", "Do it immediately.", "Last warning!", "Within 2 hours or legal action.", "Today only.", "Kindly do it fast."]
PAYMENT = [
    ("Pay to UPI {UPI_1}", ["UPI_1"]), ("Send the amount to {UPI_1|spaced}", ["UPI_1"]), ("GPay {UPI_1} and share screenshot", ["UPI_1"]),
    ("Transfer to A/c {ACCT_1} IFSC {IFSC_1}", ["ACCT_1", "IFSC_1"]), ("Account number {ACCT_1|grouped}, IFSC {IFSC_1}", ["ACCT_1", "IFSC_1"]),
    ("Call {PHONE_1} now", ["PHONE_1"]), ("WhatsApp me on {PHONE_1|cc_space}", ["PHONE_1"]), ("Contact officer {PHONE_1|spaced}", ["PHONE_1"]),
    ("Click {URL_1}", ["URL_1"]), ("Open {URL_1|https} to verify", ["URL_1"]), ("Visit {URL_1|noscheme}", ["URL_1"]),
    ("Pay {UPI_1} or call {PHONE_1}", ["UPI_1", "PHONE_1"]), ("Fill the form at {URL_1} then pay {UPI_1}", ["URL_1", "UPI_1"]),
]
BENIGN = [
    ("Your Amazon order #{ORDER_1} will be delivered today between 2 and 4 PM. No action required.", []),
    ("Rs 1,250 debited from A/c XX4821 on 05-Nov. If not done by you, call {TOLLFREE_1|spaced}.", []),
    ("{OTP_1} is your OTP for login. Do not share it with anyone.", []),
    ("Hi, are we still meeting for lunch tomorrow? Let me know if timing works.", []),
    ("Reminder: your dental appointment is on Friday at 11 am.", []),
    ("Your electricity bill of Rs 840 has been paid successfully. Thank you.", []),
    ("Beta, call me when you are free. Papa's new number is {PHONE_1}.", ["PHONE_1"]),
    ("Payment of Rs 300 to the vegetable shop successful. UPI Ref No {REF_1}.", []),
    ("Your card ending 4821 was used for Rs 799 at a supermarket. Not you? Call {TOLLFREE_1}.", []),
    ("See you at the station at 6. Bring the tickets.", []),
]


def generate(n_scam: int, n_benign: int, rng: random.Random) -> list[dict]:
    out = []
    types = sorted(OPENERS)
    for i in range(n_scam):
        t = rng.choice(types)
        pay, iocs = rng.choice(PAYMENT)
        text = " ".join(x for x in [rng.choice(OPENERS[t]), rng.choice(PRESSURE), pay + "."] if x)
        out.append({"id": f"gen-scam-{i:04d}", "source": "generated", "text": text, "iocs": iocs, "triage": "scam", "scam_type": t,
                    "lang": "en", "tags": ["generated"], "turn": "opener"})
    for i in range(n_benign):
        text, iocs = rng.choice(BENIGN)
        out.append({"id": f"gen-benign-{i:04d}", "source": "generated", "text": text, "iocs": iocs, "triage": "benign", "scam_type": "",
                    "lang": "en", "tags": ["generated"], "turn": "opener"})
    return out


def load_handwritten(path: Path = HANDWRITTEN) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_corpus(seed: int, n_scam: int = 300, n_benign: int = 100) -> list[dict]:
    rng = random.Random(seed)
    records = load_handwritten() + generate(n_scam, n_benign, random.Random(seed + 1))
    return [render(r, rng) | {"seed": seed} for r in records]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(HERE / "data" / "corpus.jsonl"))
    a = ap.parse_args(argv)
    recs = build_corpus(a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    print(f"wrote {len(recs)} synthetic records to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
