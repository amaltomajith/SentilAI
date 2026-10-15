"""Simulation scenarios (ported from v1). Benign ones exist to prove honest triage: Sentinel must NOT engage them."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str  # scam | safe
    type: str
    message: str


SCENARIOS = [
    Scenario("kyc-phishing", "scam", "KYC Phishing", "Dear user, your SBI KYC is expired. Click http://sbi-update.com or account blocked. Call 9876543210 immediately."),
    Scenario("upi-threat", "scam", "UPI Threat", "URGENT: Pay electricity bill Rs 800 to power@paytm immediately or power cut tonight. Last warning!"),
    Scenario("sextortion", "scam", "Sextortion", "I have your private video. Pay Rs 5000 to blackmail@ybl within 24 hours or I send to your contacts."),
    Scenario("crypto", "scam", "Crypto Fraud", "Invest in Bitcoin x2 returns guaranteed! Join now: https://telegram.me/fakecrypto. Minimum Rs 10000."),
    Scenario("lottery", "scam", "Lottery Fraud", "Congratulations! You won Rs 50 Lakhs in Jio Lucky Draw! Send Rs 500 processing fee to lottery@okaxis. Ref: HDFC0001234"),
    Scenario("police", "scam", "Police Impersonation", "This is CBI calling. Your Aadhaar linked to money laundering case. Transfer Rs 25000 to clear your name. UPI: cbi.officer@ybl. Call 8765432109."),
    Scenario("job", "scam", "Fake Job", "Work from home! Earn Rs 5000/day typing. Registration fee Rs 999 only. Pay to jobs@upi. Visit http://easy-money-jobs.com"),
    Scenario("tea", "safe", "Genuine Chat", "Hi, are we still meeting for tea at 5 PM? Let me know if timing works."),
    Scenario("delivery", "safe", "Genuine Delivery", "Your Amazon order #12345 will be delivered today between 2-4 PM. No action required."),
    Scenario("bank-alert", "safe", "Genuine Bank Alert", "SBI Alert: Rs 5000 debited from A/c XX1234 on 05-Feb. If not done by you, call 1800111222."),
]
BY_ID = {s.id: s for s in SCENARIOS}


def pick(scenario_id: str | None = None, rng: random.Random | None = None) -> Scenario:
    if scenario_id:
        return BY_ID[scenario_id]
    return (rng or random).choice([s for s in SCENARIOS if s.category == "scam"])