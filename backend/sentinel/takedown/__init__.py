"""Approval-gated takedown drafts. STIX 2.1 bundle + formal abuse report per target.
Only `dry_run` dispatch exists: it writes the report to disk and never contacts anyone."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import stix2
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from sentinel import ledger
from sentinel.db.models import CanaryHit, Canary, Ioc, Session, Takedown
from sentinel.enrich import BANKS, enrich_domain, enrich_ifsc

OUTBOX = Path(__file__).resolve().parents[2] / "data" / "outbox"


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace("'", "\\'")


def _pattern(kind: str, value: str) -> str | None:
    v = _esc(value)
    if kind == "url":
        return f"[url:value = '{v}']"
    if kind == "domain":
        return f"[domain-name:value = '{v}']"
    if kind == "upi":
        return f"[user-account:account_login = '{v}' AND user-account:account_type = 'upi']"
    if kind == "bank_account":
        return f"[user-account:account_login = '{v}' AND user-account:account_type = 'bank']"
    if kind == "phone":
        return f"[user-account:account_login = '{v}' AND user-account:account_type = 'phone']"
    if kind == "ipv4":
        return f"[ipv4-addr:value = '{v}']"
    return None


def build_bundle(session: Session, iocs: list[tuple[str, str]], head_hash: str) -> dict:
    now = datetime.now(timezone.utc)
    objs = []
    for kind, value in iocs:
        pat = _pattern(kind, value)
        if pat:
            objs.append(stix2.Indicator(name=f"{kind}: {value}"[:200], pattern=pat, pattern_type="stix", valid_from=now,
                                        labels=["malicious-activity"], description="Observed in a Sentinel honeypot session (literal-grounded)."))
    report = stix2.Report(name=f"Sentinel session {session.id[:8]}", published=now, report_types=["threat-report"],
                          object_refs=[o.id for o in objs] or [stix2.Identity(name="sentinel", identity_class="system").id],
                          description=f"Ledger head hash (sha256 chain): {head_hash}")
    return json.loads(stix2.Bundle(objects=[*objs, report], allow_custom=True).serialize())


def draft_report(target_kind: str, target: str, recipient: str, evidence: list[str], head_hash: str, session_id: str) -> str:
    lines = [
        f"To: {recipient}",
        f"Subject: Abuse report - {target_kind} {target}",
        "",
        "Dear Abuse / Fraud Desk,",
        "",
        f"We are reporting the following {target_kind} used in an active financial-fraud attempt targeting Indian users:",
        f"    {target}",
        "",
        "Evidence summary:",
        *[f"  - {e}" for e in evidence],
        "",
        f"Integrity: the full conversation log is hash-chained (SHA-256). Chain head: {head_hash}",
        f"Session reference: {session_id}",
        "A STIX 2.1 bundle is attached. Please suspend the resource and preserve related records.",
        "",
        "Regards,",
        "Sentinel operator (DRAFT - not yet sent)",
    ]
    return "\n".join(lines)


async def create_drafts(db: DbSession, session: Session, *, fetch=None, domain_fetch=None) -> list[Takedown]:
    iocs = db.scalars(select(Ioc).where(Ioc.session_id == session.id)).all()
    head = ledger.verify(db, session.id).head_hash
    hits = db.execute(select(CanaryHit).join(Canary, Canary.token == CanaryHit.token)
                      .where(Canary.session_id == session.id, CanaryHit.classification == "human")).scalars().all()
    ips = sorted({h.ip for h in hits if h.ip})
    base_pairs = [(i.kind, i.value) for i in iocs] + [("ipv4", ip) for ip in ips if ":" not in ip]
    drafts: list[Takedown] = []
    existing = {(t.target_kind, t.target) for t in db.scalars(select(Takedown).where(Takedown.session_id == session.id))}

    async def add(kind, target, recipient, evidence):
        if (kind, target) in existing:
            return
        td = Takedown(session_id=session.id, target_kind=kind, target=target, recipient=recipient,
                      bundle=build_bundle(session, [(kind, target)] + [p for p in base_pairs if p != (kind, target)], head),
                      report=draft_report(kind, target, recipient, evidence, head, session.id),
                      dispatch_mode="dry_run")
        db.add(td)
        drafts.append(td)

    domains = {urlparse(i.value).hostname for i in iocs if i.kind == "url" and urlparse(i.value).hostname}
    for d in sorted(domains):
        info = await (enrich_domain(d, fetch=domain_fetch) if domain_fetch else enrich_domain(d))
        rcpt = info.get("abuse_email") or f"abuse desk of registrar {info.get('registrar') or '(unknown - look up WHOIS)'}"
        await add("domain", d, rcpt, [f"Phishing URL observed in scammer message(s) for domain {d}",
                                      f"Registrar: {info.get('registrar')}", f"Registered: {info.get('registered')}"])
    ifscs = {i.value for i in iocs if i.kind == "ifsc"}
    for acct in [i for i in iocs if i.kind == "bank_account"]:
        bank = None
        for code in ifscs:
            info = await (enrich_ifsc(code, fetch=fetch) if fetch else enrich_ifsc(code))
            bank = info.get("bank") or BANKS.get(code[:4])
            break
        await add("bank_account", acct.value, f"Nodal fraud officer, {bank or 'beneficiary bank'} (cc: cybercrime.gov.in, 1930)",
                  ["Account supplied by the scammer as the payment destination", f"IFSC(s) given: {', '.join(sorted(ifscs)) or 'none'}"])
    for u in [i for i in iocs if i.kind == "upi"]:
        await add("upi", u.value, "NPCI dispute / fraud desk and the issuing PSP (cc: cybercrime.gov.in, 1930)",
                  ["UPI ID supplied by the scammer as the payment destination"])
    for d in drafts:
        db.flush()
    return drafts


def approve(db: DbSession, td_id: str, approve_it: bool = True) -> Takedown:
    td = db.get(Takedown, td_id)
    if td is None:
        raise KeyError(td_id)
    if td.status != "drafted":
        raise ValueError(f"cannot change a takedown in state {td.status}")
    td.status = "approved" if approve_it else "rejected"
    td.decided_at = datetime.now(timezone.utc)
    return td


def dispatch(db: DbSession, td_id: str, mode: str = "dry_run") -> Takedown:
    td = db.get(Takedown, td_id)
    if td is None:
        raise KeyError(td_id)
    if td.status != "approved":
        raise PermissionError("takedown must be approved by an operator before dispatch")
    if mode != "dry_run":
        raise NotImplementedError("real dispatch is intentionally not implemented; only dry_run exists")
    OUTBOX.mkdir(parents=True, exist_ok=True)
    (OUTBOX / f"{td.id}.report.txt").write_text(td.report, encoding="utf-8")
    (OUTBOX / f"{td.id}.stix.json").write_text(json.dumps(td.bundle, indent=2), encoding="utf-8")
    td.status, td.dispatch_mode = "dispatched", "dry_run"
    return td