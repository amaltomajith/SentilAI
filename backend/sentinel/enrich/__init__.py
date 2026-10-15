"""Free OSINT enrichment: UPI PSP handles, IFSC (offline prefix table + ifsc.razorpay.com), RDAP, ip-api.com.
All network access goes through the SSRF guard; every function takes an injectable `fetch`."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from sentinel.security import safe_get_json

PSP = {
    "ybl": ("PhonePe", "Yes Bank"), "ibl": ("PhonePe", "ICICI Bank"), "axl": ("PhonePe", "Axis Bank"),
    "paytm": ("Paytm", "Paytm Payments Bank"), "pthdfc": ("Paytm", "HDFC Bank"), "ptyes": ("Paytm", "Yes Bank"),
    "ptsbi": ("Paytm", "State Bank of India"), "okaxis": ("Google Pay", "Axis Bank"),
    "okhdfcbank": ("Google Pay", "HDFC Bank"), "okicici": ("Google Pay", "ICICI Bank"),
    "oksbi": ("Google Pay", "State Bank of India"), "apl": ("Amazon Pay", "Axis Bank"),
    "yapl": ("Amazon Pay", "Yes Bank"), "rapl": ("Amazon Pay", "RBL Bank"),
    "upi": ("BHIM", "NPCI"), "sbi": ("SBI Pay", "State Bank of India"), "hdfcbank": ("HDFC PayZapp", "HDFC Bank"),
    "icici": ("iMobile", "ICICI Bank"), "axisbank": ("Axis Mobile", "Axis Bank"), "kotak": ("Kotak 811", "Kotak Mahindra Bank"),
    "ikwik": ("MobiKwik", "-"), "freecharge": ("Freecharge", "Axis Bank"), "jupiteraxis": ("Jupiter", "Axis Bank"),
    "fbl": ("Federal Bank", "Federal Bank"), "postbank": ("India Post Payments Bank", "IPPB"),
    "airtel": ("Airtel Payments Bank", "Airtel Payments Bank"), "waicici": ("WhatsApp Pay", "ICICI Bank"),
}
BANKS = {
    "SBIN": "State Bank of India", "HDFC": "HDFC Bank", "ICIC": "ICICI Bank", "UTIB": "Axis Bank", "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda", "CNRB": "Canara Bank", "UBIN": "Union Bank of India", "KKBK": "Kotak Mahindra Bank",
    "IDIB": "Indian Bank", "BKID": "Bank of India", "YESB": "Yes Bank", "INDB": "IndusInd Bank", "FDRL": "Federal Bank",
    "IOBA": "Indian Overseas Bank", "MAHB": "Bank of Maharashtra", "CBIN": "Central Bank of India", "UCBA": "UCO Bank",
    "PYTM": "Paytm Payments Bank", "AIRP": "Airtel Payments Bank", "IPOS": "India Post Payments Bank",
    "RATN": "RBL Bank", "KARB": "Karnataka Bank", "SIBL": "South Indian Bank", "IDFB": "IDFC First Bank",
}
IFSC_FORMAT = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_cache: dict[str, dict] = {}


def enrich_upi(vpa: str) -> dict:
    if "@" not in vpa:
        return {"valid": False}
    user, handle = vpa.rsplit("@", 1)
    app, bank = PSP.get(handle.lower(), (None, None))
    return {"valid": True, "handle": handle, "psp_app": app, "issuing_bank": bank, "known_handle": app is not None,
            "note": None if app else "unknown PSP handle (possible typo-squat or niche PSP)"}


async def enrich_ifsc(code: str, fetch=safe_get_json) -> dict:
    code = code.upper()
    if not IFSC_FORMAT.match(code):
        return {"valid": False}
    base = {"valid": True, "bank": BANKS.get(code[:4]), "source": "offline-prefix"}
    if code in _cache:
        return _cache[code]
    try:
        d = await fetch(f"https://ifsc.razorpay.com/{code}")
        if isinstance(d, dict) and d.get("BANK"):
            base = {"valid": True, "bank": d.get("BANK"), "branch": d.get("BRANCH"), "city": d.get("CITY"),
                    "district": d.get("DISTRICT"), "state": d.get("STATE"), "address": d.get("ADDRESS"),
                    "source": "ifsc.razorpay.com"}
    except Exception as e:  # offline / unknown IFSC: keep the prefix-only answer
        base["lookup_error"] = type(e).__name__
    _cache[code] = base
    return base


async def enrich_domain(url_or_domain: str, fetch=safe_get_json) -> dict:
    host = (urlparse(url_or_domain).hostname if "://" in url_or_domain else url_or_domain).lower().strip(".")
    out = {"domain": host, "source": "rdap.org"}
    try:
        d = await fetch(f"https://rdap.org/domain/{host}")
        out["registrar"] = None
        out["abuse_email"] = None
        for ent in d.get("entities", []) if isinstance(d, dict) else []:
            roles = ent.get("roles", [])
            vc = (ent.get("vcardArray") or [None, []])[1]
            fields = {i[0]: i[3] for i in vc if len(i) > 3}
            if "registrar" in roles:
                out["registrar"] = fields.get("fn")
            for sub in ent.get("entities", []):
                if "abuse" in sub.get("roles", []):
                    svc = (sub.get("vcardArray") or [None, []])[1]
                    for i in svc:
                        if len(i) > 3 and i[0] == "email":
                            out["abuse_email"] = i[3]
            if "abuse" in roles and not out["abuse_email"]:
                out["abuse_email"] = fields.get("email")
        for ev in d.get("events", []) if isinstance(d, dict) else []:
            if ev.get("eventAction") == "registration":
                out["registered"] = ev.get("eventDate")
        out["status"] = d.get("status") if isinstance(d, dict) else None
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:200]
    return out


async def enrich_ip(ip: str, fetch=safe_get_json) -> dict:
    """ip-api.com free tier (HTTP only, 45 req/min). Returns {} on failure; never blocks a canary hit."""
    try:
        d = await fetch(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,as,asname,mobile,proxy,hosting")
        if isinstance(d, dict) and d.get("status") == "success":
            return {"asn": d.get("as"), "asname": d.get("asname"), "isp": d.get("isp"), "org": d.get("org"),
                    "country": d.get("country"), "region": d.get("regionName"), "city": d.get("city"),
                    "mobile": d.get("mobile"), "proxy": d.get("proxy"), "hosting": d.get("hosting")}
    except Exception:
        pass
    return {}