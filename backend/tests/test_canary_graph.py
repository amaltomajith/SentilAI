from sentinel import ledger
from sentinel.canary import attach_fingerprint, classify, is_alert, mint, og_html, decoy_html, record_hit
from sentinel.db.models import Ioc, Session
from sentinel.graph import attribution
from sentinel.grounding import extract_grounded

CRAWLERS = [
    {"User-Agent": "WhatsApp/2.23.20.0 A"},
    {"User-Agent": "TelegramBot (like TwitterBot)"},
    {"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"},
    {"User-Agent": "Twitterbot/1.0"},
    {"User-Agent": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"},
    {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"},
    {"User-Agent": "curl/8.4.0"},
    {"User-Agent": "python-requests/2.31"},
    {"User-Agent": ""},
    {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36", "Accept": "*/*"},  # browser-ish UA but no HTML accept / language
]
HUMANS = [
    {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-A135F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
     "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-IN,hi;q=0.9", "Sec-Fetch-Mode": "navigate"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
     "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-IN"},
]


def test_classifier_fixtures():
    assert all(classify(h) == "crawler" for h in CRAWLERS)
    assert all(classify(h) == "human" for h in HUMANS)


def _hits(db, sess, classifier):
    c = mint(db, sess, "receipt", "https://sentinel.example")
    return [record_hit(db, c["token"], ip="1.2.3.4", headers=h, classifier=classifier) for h in CRAWLERS]


def test_positive_control_naive_classifier_raises_false_alerts(db, sess):
    naive = lambda headers: "human"            # guard disabled: every fetch looks like an attacker
    alerts = [h for h in _hits(db, sess, naive) if is_alert(h)]
    assert len(alerts) == len(CRAWLERS)         # proves this test CAN fail


def test_real_classifier_raises_zero_false_alerts(db, sess):
    assert [h for h in _hits(db, sess, classify) if is_alert(h)] == []


def test_human_hit_alerts_and_fingerprint_attaches_and_ledger_verifies(db, sess):
    c = mint(db, sess, "kyc", "https://sentinel.example")
    hit = record_hit(db, c["token"], ip="49.36.10.77", headers=HUMANS[0], ip_intel={"asn": "AS55836", "isp": "Reliance Jio"})
    assert is_alert(hit) and hit.subnet == "49.36.10.0/24" and hit.isp == "Reliance Jio"
    fp = {"screen": "1080x2400", "platform": "Linux armv8l", "timezone": "Asia/Kolkata", "languages": "en-IN", "webgl": "Adreno (TM) 610", "cores": 8, "memory": 4, "touch": 5, "colorDepth": 24}
    h2 = attach_fingerprint(db, c["token"], "49.36.10.77", fp)
    assert h2 and len(h2.fingerprint_hash) == 64
    assert ledger.verify(db, sess.id).ok


def test_unknown_token_ignored(db):
    assert record_hit(db, "nope", ip="1.1.1.1", headers=HUMANS[0]) is None


def test_minted_url_is_never_scammer_intel(db, sess):
    from sqlalchemy import select
    from sentinel.db.models import HoneyToken
    c = mint(db, sess, "receipt", "https://sentinel.example")
    honey = {h.value for h in db.scalars(select(HoneyToken))}
    assert extract_grounded(f"scammer repeats {c['url']} back", honey) == []


def test_pages_render():
    assert "og:title" in og_html("receipt", "https://x/r/t") and "<script" not in og_html("kyc", "https://x/r/t")
    d = decoy_html("abc")
    assert "/r/abc/fp" in d and "ERR_PDF_CORRUPT" in d


# ---------- graph ----------
def _s(db, ioc_list):
    s = Session(kind="live")
    db.add(s); db.flush()
    for kind, val in ioc_list:
        db.add(Ioc(session_id=s.id, kind=kind, value=val))
    db.flush()
    return s


def test_graph_clusters_one_and_two_hop_and_separates_unrelated(db):
    s1 = _s(db, [("upi", "mule@ybl")])
    s2 = _s(db, [("upi", "mule@ybl"), ("bank_account", "111111111111"), ("ifsc", "SBIN0000123")])
    s3 = _s(db, [("bank_account", "222222222222"), ("ifsc", "SBIN0000123")])     # 2-hop: same branch, different account
    s4 = _s(db, [("upi", "other@paytm")])
    out = attribution(db)
    rings = out["rings"]
    assert len(rings) == 1
    assert set(rings[0]["sessions"]) == {s1.id, s2.id, s3.id} and s4.id not in rings[0]["sessions"]
    assert rings[0]["confidence"] == "mixed"           # s3 attached only via weak IFSC link
    assert any(n["type"] == "session" for n in out["nodes"]) and out["edges"]


def test_weak_only_link_is_low_confidence(db):
    a = _s(db, [("ifsc", "HDFC0000001")]); b = _s(db, [("ifsc", "HDFC0000001")])
    r = attribution(db)["rings"]
    assert len(r) == 1 and r[0]["confidence"] == "low"


def test_domain_from_urls_links_sessions(db):
    a = _s(db, [("url", "http://sbi-update.com/a")]); b = _s(db, [("url", "https://sbi-update.com/other")])
    r = attribution(db)["rings"]
    assert len(r) == 1 and "domain" in r[0]["shared_artifact_kinds"]


def test_crawler_hits_and_honey_tokens_do_not_link(db):
    from sentinel.db.models import HoneyToken
    a = _s(db, []); b = _s(db, [])
    for s in (a, b):
        c = mint(db, s, "receipt", "https://sentinel.example")
        record_hit(db, c["token"], ip="9.9.9.9", headers=CRAWLERS[0])
    db.add(HoneyToken(session_id="", kind="upi", value="ramesh@oksbi"))
    db.add(Ioc(session_id=a.id, kind="upi", value="ramesh@oksbi")); db.add(Ioc(session_id=b.id, kind="upi", value="ramesh@oksbi"))
    db.flush()
    assert attribution(db)["rings"] == []


def test_human_canary_subnet_and_fingerprint_link(db):
    fp = {"screen": "1080x2400", "platform": "Linux armv8l", "timezone": "Asia/Kolkata", "languages": "en-IN", "webgl": "Adreno 610", "cores": 8, "memory": 4, "touch": 5, "colorDepth": 24}
    a = _s(db, []); b = _s(db, [])
    for s, ip in ((a, "49.36.10.5"), (b, "49.36.10.200")):
        c = mint(db, s, "kyc", "https://sentinel.example")
        record_hit(db, c["token"], ip=ip, headers=HUMANS[0]); attach_fingerprint(db, c["token"], ip, fp)
    r = attribution(db)["rings"]
    assert len(r) == 1 and {"fingerprint", "subnet"} <= set(r[0]["shared_artifact_kinds"]) and r[0]["confidence"] == "high"