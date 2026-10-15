"""Canary links: mint, classify crawler-vs-human, serve OpenGraph to bots and a decoy to humans."""
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import secrets
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from sentinel import ledger
from sentinel.db.models import Canary, CanaryHit, HoneyToken, Session

CRAWLER_UA = [
    "whatsapp", "telegrambot", "facebookexternalhit", "facebot", "twitterbot", "slackbot", "slack-imgproxy",
    "linkedinbot", "discordbot", "skypeuripreview", "googlebot", "google-pagerenderer", "bingbot", "applebot",
    "pinterestbot", "redditbot", "embedly", "vkshare", "viber", "line-poker", "signal", "curl/", "python-requests",
    "go-http-client", "okhttp/", "headlesschrome", "bot/", "crawler", "spider", "preview",
]


def classify(headers: dict[str, str]) -> str:
    """'crawler' | 'human'. Signature match wins; otherwise a request must look like a real browser navigation
    (Accept-Language + HTML Accept, and Sec-Fetch-* or a classic browser UA) to count as human."""
    h = {k.lower(): v for k, v in headers.items()}
    ua = h.get("user-agent", "").lower()
    if not ua or any(sig in ua for sig in CRAWLER_UA):
        return "crawler"
    accepts_html = "text/html" in h.get("accept", "")
    has_lang = bool(h.get("accept-language"))
    sec_nav = h.get("sec-fetch-mode", "").lower() == "navigate"
    browserish = ("mozilla/" in ua) and (sec_nav or "applewebkit" in ua or "gecko" in ua)
    return "human" if (accepts_html and has_lang and browserish) else "crawler"


def subnet_of(ip: str) -> str:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    prefix = 24 if a.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def fingerprint_hash(fp: dict) -> str:
    stable = {k: fp.get(k) for k in ("screen", "platform", "timezone", "languages", "webgl", "cores", "memory", "touch", "colorDepth")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def mint(db: DbSession, session: Session, kind: str, base_url: str) -> dict:
    token = secrets.token_urlsafe(12)
    db.add(Canary(token=token, session_id=session.id, kind=kind))
    url = f"{base_url.rstrip('/')}/r/{token}"
    # Our own link must never be recorded as scammer intel.
    db.add(HoneyToken(session_id=session.id, kind="url", value=url))
    db.add(HoneyToken(session_id=session.id, kind="url", value=urlparse(url).hostname or ""))
    db.flush()
    return {"token": token, "url": url, "kind": kind}


def og_html(kind: str, url: str) -> str:
    title, desc = (("UPI Payment Receipt - Transaction Pending", "Your payment receipt is ready. Tap to view and download PDF.")
                   if kind == "receipt" else ("KYC Verification - Action Required", "Complete your KYC verification to avoid account restriction."))
    t, d, u = html.escape(title), html.escape(desc), html.escape(url)
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{t}</title>'
            f'<meta property="og:type" content="website"><meta property="og:title" content="{t}">'
            f'<meta property="og:description" content="{d}"><meta property="og:url" content="{u}">'
            f'<meta name="twitter:card" content="summary"><meta name="description" content="{d}"></head>'
            f'<body>{t}</body></html>')


def decoy_html(token: str) -> str:
    return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Receipt</title><style>body{font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}
.c{background:#fff;border-radius:12px;padding:28px;max-width:360px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.1)}
.e{color:#c62828;font-weight:600;margin:12px 0}.s{color:#777;font-size:13px}</style></head><body><div class="c">
<div style="font-size:42px">&#9888;</div><div class="e">Receipt Server Error</div>
<div>Unable to open PDF: the file appears to be corrupted.</div><div class="s">Error code: ERR_PDF_CORRUPT (0x80070570)<br>Please try again in a few minutes.</div></div>
<script>(function(){try{var c=document.createElement('canvas'),g=c.getContext('webgl')||c.getContext('experimental-webgl'),w='';
if(g){var e=g.getExtension('WEBGL_debug_renderer_info');w=e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)}
var fp={screen:screen.width+'x'+screen.height,colorDepth:screen.colorDepth,platform:navigator.platform,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
languages:(navigator.languages||[navigator.language]).join(','),webgl:w,cores:navigator.hardwareConcurrency||0,memory:navigator.deviceMemory||0,touch:navigator.maxTouchPoints||0};
fetch('/r/TOKEN/fp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fp),keepalive:true})}catch(x){}})();</script></body></html>""".replace("TOKEN", token)


def record_hit(db: DbSession, token: str, *, ip: str, headers: dict, ip_intel: dict | None = None,
               classifier=classify) -> CanaryHit | None:
    can = db.get(Canary, token)
    if can is None:
        return None
    cls = classifier(headers)
    intel = ip_intel or {}
    hit = CanaryHit(token=token, classification=cls, ip=ip, subnet=subnet_of(ip), asn=str(intel.get("asn") or ""),
                    isp=str(intel.get("isp") or ""), user_agent=headers.get("user-agent", headers.get("User-Agent", "")),
                    headers={k.lower(): v for k, v in headers.items() if k.lower() in
                             ("user-agent", "accept", "accept-language", "referer", "sec-fetch-mode", "sec-ch-ua", "x-requested-with")})
    db.add(hit)
    db.flush()
    sess = db.get(Session, can.session_id)
    if sess is not None:
        ledger.append(db, sess, "canary_hit", {"token": token, "classification": cls, "ip": ip, "subnet": hit.subnet,
                                               "asn": hit.asn, "isp": hit.isp})
    return hit


def attach_fingerprint(db: DbSession, token: str, ip: str, fp: dict) -> CanaryHit | None:
    hit = db.scalar(select(CanaryHit).where(CanaryHit.token == token, CanaryHit.classification == "human", CanaryHit.ip == ip)
                    .order_by(CanaryHit.created_at.desc()).limit(1))
    if hit is None:
        return None
    hit.fingerprint = {k: fp.get(k) for k in ("screen", "colorDepth", "platform", "timezone", "languages", "webgl", "cores", "memory", "touch")}
    hit.fingerprint_hash = fingerprint_hash(fp)
    can = db.get(Canary, token)
    sess = db.get(Session, can.session_id) if can else None
    if sess is not None:
        ledger.append(db, sess, "canary_hit", {"token": token, "fingerprint_hash": hit.fingerprint_hash, "fingerprint": hit.fingerprint})
    return hit


def is_alert(hit: CanaryHit) -> bool:
    """An attacker alert is raised only for classified-human hits."""
    return hit.classification == "human"