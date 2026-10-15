import json
import socket

import httpx
import pytest

from sentinel.enrich import enrich_domain, enrich_ifsc, enrich_upi
from sentinel.security import SSRFBlocked, is_public_ip, safe_get_json, sign, validate_url, verify_signature


def fake_resolver(mapping):
    def r(host, port, *a, **k):
        if host not in mapping:
            raise socket.gaierror("nx")
        return [(socket.AF_INET, 0, 0, "", (ip, 0)) for ip in mapping[host]]
    return r


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "172.16.0.1", "::1",
                                "100.64.0.1", "0.0.0.0", "::ffff:127.0.0.1", "fe80::1"])
def test_private_ranges_blocked(ip):
    assert not is_public_ip(ip)


def test_public_ip_allowed():
    assert is_public_ip("8.8.8.8")


@pytest.mark.parametrize("url", ["http://localhost/", "http://169.254.169.254/latest/meta-data", "http://127.0.0.1:80/",
                                 "ftp://example.com/x", "http://user:pw@example.com/", "http://example.com:8080/",
                                 "file:///etc/passwd", "http://[::1]/"])
def test_bad_urls_blocked(url):
    with pytest.raises(SSRFBlocked):
        validate_url(url, fake_resolver({"example.com": ["93.184.216.34"], "localhost": ["127.0.0.1"]}))


def naive_validate(url: str) -> bool:
    """What an undefended implementation does: block obviously-internal *hostnames*, never look at what DNS returns."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return urlparse(url).scheme in ("http", "https") and host not in ("localhost", "127.0.0.1", "::1", "169.254.169.254")


REBIND = fake_resolver({"evil.example": ["93.184.216.34", "127.0.0.1"], "metadata.evil.example": ["169.254.169.254"]})


@pytest.mark.parametrize("url", ["http://evil.example/", "http://metadata.evil.example/latest/meta-data/"])
def test_positive_control_naive_check_is_fooled_by_dns_but_guard_is_not(url):
    assert naive_validate(url) is True                      # the attack lands against a hostname-only check
    with pytest.raises(SSRFBlocked):
        validate_url(url, REBIND)                           # the real guard resolves and rejects every address


def test_decimal_ip_encoding_blocked():
    with pytest.raises(SSRFBlocked):
        validate_url("http://2130706433/")  # 127.0.0.1 as an integer


async def test_redirect_to_internal_blocked():
    def handler(req):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
    with pytest.raises(SSRFBlocked):
        await safe_get_json("https://good.example/x", resolver=fake_resolver({"good.example": ["93.184.216.34"]}),
                            transport=httpx.MockTransport(handler))


async def test_safe_get_connects_to_validated_ip_and_returns_json():
    seen = {}
    def handler(req):
        seen["host"], seen["url"] = req.headers["host"], str(req.url)
        return httpx.Response(200, json={"ok": 1})
    r = await safe_get_json("https://good.example/x", resolver=fake_resolver({"good.example": ["93.184.216.34"]}),
                            transport=httpx.MockTransport(handler))
    assert r == {"ok": 1} and seen["host"] == "good.example" and "93.184.216.34" in seen["url"]


# ---- HMAC ----
SECRET = "s" * 40
def test_hmac_valid_and_tamper_cases():
    body = b'{"a":1}'
    sig = sign(SECRET, "POST", "/bridge/inbound", 1000, "nonce12345", body)
    assert verify_signature(SECRET, "POST", "/bridge/inbound", 1000, "nonce12345", body, sig, now=1010)[0]
    assert not verify_signature(SECRET, "POST", "/bridge/inbound", 1000, "nonce12345", b'{"a":2}', sig, now=1010)[0]
    assert not verify_signature(SECRET, "POST", "/other", 1000, "nonce12345", body, sig, now=1010)[0]
    assert not verify_signature(SECRET, "POST", "/bridge/inbound", 1000, "nonce12345", body, sig, now=1200)[0]  # expired
    assert not verify_signature(SECRET, "POST", "/bridge/inbound", 1000, "nonce12345", body, "", now=1010)[0]
    assert not verify_signature("", "POST", "/bridge/inbound", 1000, "nonce12345", body, sig, now=1010)[0]  # unconfigured secret


# ---- enrichment ----
def test_upi_enrichment():
    assert enrich_upi("x@ybl")["psp_app"] == "PhonePe"
    assert enrich_upi("x@oksbi")["issuing_bank"] == "State Bank of India"
    assert enrich_upi("x@weirdpsp")["known_handle"] is False


async def test_ifsc_offline_fallback_and_live():
    async def boom(url):
        raise RuntimeError("offline")
    r = await enrich_ifsc("SBIN0001234", fetch=boom)
    assert r["bank"] == "State Bank of India" and r["source"] == "offline-prefix"
    async def live(url):
        return {"BANK": "State Bank of India", "BRANCH": "Rampur", "CITY": "Rampur", "STATE": "UP"}
    r2 = await enrich_ifsc("SBIN0005678", fetch=live)
    assert r2["branch"] == "Rampur" and r2["source"] == "ifsc.razorpay.com"
    assert (await enrich_ifsc("BADCODE"))["valid"] is False


async def test_rdap_parsing_extracts_registrar_and_abuse():
    sample = {"status": ["active"], "events": [{"eventAction": "registration", "eventDate": "2026-09-01T00:00:00Z"}],
              "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Namecheap, Inc."]]],
                            "entities": [{"roles": ["abuse"], "vcardArray": ["vcard", [["email", {}, "text", "abuse@namecheap.com"]]]}]}]}
    async def f(url):
        return sample
    r = await enrich_domain("http://sbi-update.com/kyc", fetch=f)
    assert r["domain"] == "sbi-update.com" and r["registrar"] == "Namecheap, Inc." and r["abuse_email"] == "abuse@namecheap.com"