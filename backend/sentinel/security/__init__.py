"""SSRF guard + HMAC request signing for the WhatsApp bridge."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
import time
from urllib.parse import urlparse

import httpx

ALLOWED_PORTS = {80, 443, None}
MAX_REDIRECTS = 3
MAX_BYTES = 512 * 1024


class SSRFBlocked(Exception):
    pass


def is_public_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved
                or a.is_unspecified or (a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10")))


def resolve_public(host: str, resolver=socket.getaddrinfo) -> list[str]:
    """Resolve and require EVERY address to be public (defeats mixed A-record rebinding)."""
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        try:
            ips = sorted({ai[4][0] for ai in resolver(host, None)})
        except socket.gaierror as e:
            raise SSRFBlocked(f"cannot resolve {host}") from e
    if not ips:
        raise SSRFBlocked("no addresses")
    for ip in ips:
        if not is_public_ip(ip):
            raise SSRFBlocked(f"{host} resolves to non-public address {ip}")
    return ips


def validate_url(url: str, resolver=socket.getaddrinfo) -> tuple[str, str, list[str]]:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise SSRFBlocked("scheme not allowed")
    if p.username or p.password:
        raise SSRFBlocked("credentials in URL not allowed")
    if not p.hostname:
        raise SSRFBlocked("no host")
    if p.port not in ALLOWED_PORTS:
        raise SSRFBlocked("port not allowed")
    return p.scheme, p.hostname, resolve_public(p.hostname, resolver)


async def safe_get_json(url: str, *, resolver=socket.getaddrinfo, transport: httpx.AsyncBaseTransport | None = None,
                        timeout: float = 8.0, headers: dict | None = None) -> dict | list:
    """GET JSON from a public host. Each hop is re-validated and connected to the *validated IP*
    (Host/SNI preserved), so DNS can't be rebound between check and use."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, ips = validate_url(current, resolver)
        p = urlparse(current)
        target = current.replace(f"//{p.netloc}", f"//{ips[0] if ':' not in ips[0] else '[' + ips[0] + ']'}"
                                 + (f":{p.port}" if p.port else ""), 1)
        h = {"Host": p.netloc, "Accept": "application/json", "User-Agent": "sentinel-osint/2.0", **(headers or {})}
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False,
                                     verify=transport is None) as c:
            ext = {"sni_hostname": host} if scheme == "https" else {}
            r = await c.get(target, headers=h, extensions=ext)
        if r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers:
            current = str(httpx.URL(current).join(r.headers["location"]))
            continue
        r.raise_for_status()
        if len(r.content) > MAX_BYTES:
            raise SSRFBlocked("response too large")
        return r.json()
    raise SSRFBlocked("too many redirects")


# ---------------- bridge HMAC ----------------
MAX_SKEW_S = 60


def sign(secret: str, method: str, path: str, ts: int, nonce: str, body: bytes) -> str:
    msg = b"\n".join([method.upper().encode(), path.encode(), str(ts).encode(), nonce.encode(),
                      hashlib.sha256(body).hexdigest().encode()])
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_signature(secret: str, method: str, path: str, ts: int, nonce: str, body: bytes, sig: str,
                     now: float | None = None) -> tuple[bool, str]:
    if not secret or len(secret) < 16:
        return False, "server secret not configured"
    if abs((now if now is not None else time.time()) - ts) > MAX_SKEW_S:
        return False, "timestamp outside allowed window"
    if not nonce or len(nonce) < 8:
        return False, "bad nonce"
    if not hmac.compare_digest(sign(secret, method, path, ts, nonce, body), sig or ""):
        return False, "bad signature"
    return True, "ok"