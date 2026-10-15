"""Deterministic ploy selection: what the agent should try next is a pure function of captured vs missing IOCs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ploy:
    id: str
    targets: tuple[str, ...]
    instruction: str


PLOYS = {
    "ask_payment_rail": Ploy("ask_payment_rail", ("upi",),
        "Say you are ready to pay but do not know where. Kindly ask for the exact UPI ID to send money to."),
    "upi_daily_limit": Ploy("upi_daily_limit", ("bank_account", "ifsc"),
        "Say your UPI payment failed with 'daily limit exceeded' error. Ask for bank Account Number and IFSC code to do IMPS transfer instead."),
    "need_ifsc": Ploy("need_ifsc", ("ifsc",),
        "Say the bank app is asking for IFSC code too and you cannot proceed. Kindly ask for the IFSC code and branch."),
    "need_upi_backup": Ploy("need_upi_backup", ("upi",),
        "Say IMPS is showing server error. Ask if they have any UPI ID or GPay/PhonePe number instead."),
    "ask_callback_number": Ploy("ask_callback_number", ("phone",),
        "Say the app keeps failing and you are nervous. Ask for a phone number to call and sort it out with a human."),
    "link_not_opening": Ploy("link_not_opening", ("url",),
        "Say the link is not opening on your phone. Ask them to send the payment page link again."),
    "screenshot_error": Ploy("screenshot_error", (),
        "Say payment failed again and you will send a screenshot of the error. Ask what name/UPI should be shown."),
    "card_ready_stall": Ploy("card_ready_stall", (),
        "Say you have your debit card in hand and ask exactly what to type, step by step."),
    "official_verification_stall": Ploy("official_verification_stall", ("phone",),
        "Say you want to write down their name, employee ID and office phone number so you can quote it to your bank or family before doing anything. Ask for those."),
    "family_consult": Ploy("family_consult", ("phone",),
        "Say someone in your family usually handles money matters and you want them to talk to the sender. Ask for a phone number they can call."),
    "partial_test_payment": Ploy("partial_test_payment", ("upi", "bank_account"),
        "Say you want to send a tiny test amount first to be safe. Ask for the exact UPI ID or account number and the account holder name to use."),
    "ask_beneficiary_name": Ploy("ask_beneficiary_name", (),
        "Say your app shows a confirmation screen with the receiver's name and you want to check it before pressing pay. Ask what name should appear."),
    "wind_down": Ploy("wind_down", (),
        "Say you must go for your medicine and will try again later. Stay polite and brief."),
}


def ploy_order(captured: set[str] | frozenset[str], turn_count: int, scam_type: str = "") -> list[str]:
    """Playbook candidates, best first. The first entry is the deterministic default; the adaptive chooser may pick a later one."""
    c = set(captured)
    order = []
    if scam_type in ("police_impersonation", "kyc_bank", "tech_support") and "phone" not in c and turn_count >= 1:
        order.append("official_verification_stall")
    if "upi" not in c and "bank_account" not in c:
        order.append("ask_payment_rail")
    if "upi" in c and "bank_account" not in c:
        order.append("upi_daily_limit")
    if "bank_account" in c and "ifsc" not in c:
        order.append("need_ifsc")
    if "bank_account" in c and "upi" not in c:
        order.append("need_upi_backup")
    if "phone" not in c:
        order.append("ask_callback_number")
    if "url" not in c and turn_count >= 3:
        order.append("link_not_opening")
    if "phone" not in c and turn_count >= 2:
        order.append("family_consult")
    if ("upi" not in c or "bank_account" not in c) and turn_count >= 2:
        order.append("partial_test_payment")
    order.append("ask_beneficiary_name")
    order.append("card_ready_stall")
    return order


def select_ploy(captured: set[str] | frozenset[str], turn_count: int, last_ploy: str = "", scammer_asked_screenshot: bool = False) -> Ploy:
    if turn_count >= 10:
        return PLOYS["wind_down"]
    if scammer_asked_screenshot:
        return PLOYS["screenshot_error"]
    order = [p for p in ploy_order(captured, turn_count) if p not in ("official_verification_stall", "family_consult", "partial_test_payment", "ask_beneficiary_name")]
    for pid in order:
        if pid != last_ploy:
            return PLOYS[pid]
    return PLOYS[order[0]]


def missing_targets(captured) -> list[str]:
    return [k for k in ("upi", "bank_account", "ifsc", "phone", "url") if k not in set(captured)]