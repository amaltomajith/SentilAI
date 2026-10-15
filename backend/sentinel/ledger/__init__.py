"""Tamper-evident, hash-chained event ledger (one chain per session).

hash_n = SHA256( prev_hash || canonical_json({session_id, seq, type, created_at, payload}) )

Any edit, deletion, insertion or reordering of an event breaks verification from that point on.
A hash chain proves *internal consistency*. Someone controlling the whole DB could rebuild it, so the
head hash should be anchored externally (it is printed on forensic PDFs).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from sentinel.db.models import LedgerEvent, Session

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, session_id: str, seq: int, type_: str, created_at: str, payload: dict) -> str:
    body = canonical({"session_id": session_id, "seq": seq, "type": type_, "created_at": created_at, "payload": payload})
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def append(db: DbSession, session: Session, type_: str, payload: dict) -> LedgerEvent:
    last = db.scalar(
        select(LedgerEvent).where(LedgerEvent.session_id == session.id).order_by(LedgerEvent.seq.desc()).limit(1)
    )
    seq = (last.seq + 1) if last else 1
    prev = last.hash if last else GENESIS
    created = datetime.now(timezone.utc).isoformat()
    clean = json.loads(canonical(payload))  # round-trip so the stored payload hashes identically on re-read
    ev = LedgerEvent(
        session_id=session.id, seq=seq, type=type_, payload=clean, created_at=created, prev_hash=prev,
        hash=compute_hash(prev, session.id, seq, type_, created, clean),
    )
    db.add(ev)
    session.head_hash = ev.hash
    db.flush()
    return ev


@dataclass
class VerifyResult:
    ok: bool
    checked: int
    head_hash: str
    bad_seq: int | None = None
    reason: str = ""


def verify(db: DbSession, session_id: str) -> VerifyResult:
    events = db.scalars(
        select(LedgerEvent).where(LedgerEvent.session_id == session_id).order_by(LedgerEvent.seq)
    ).all()
    prev = GENESIS
    for i, ev in enumerate(events, start=1):
        if ev.seq != i:
            return VerifyResult(False, i - 1, prev, ev.seq, f"sequence gap: expected {i}, found {ev.seq}")
        if ev.prev_hash != prev:
            return VerifyResult(False, i - 1, prev, ev.seq, "prev_hash does not match previous event")
        if compute_hash(prev, session_id, ev.seq, ev.type, ev.created_at, ev.payload) != ev.hash:
            return VerifyResult(False, i - 1, prev, ev.seq, "event content does not match its hash")
        prev = ev.hash
    sess = db.get(Session, session_id)
    if sess is not None and sess.head_hash != prev:
        return VerifyResult(False, len(events), prev, None, "session head_hash does not match chain tip (truncation?)")
    return VerifyResult(True, len(events), prev)


def export_proof(db: DbSession, session_id: str) -> dict:
    """Self-contained proof embedded in forensic reports; checkable offline with `verify_proof`."""
    events = db.scalars(
        select(LedgerEvent).where(LedgerEvent.session_id == session_id).order_by(LedgerEvent.seq)
    ).all()
    res = verify(db, session_id)
    return {
        "session_id": session_id,
        "algorithm": "sha256 chain: H(prev || canonical_json(session_id,seq,type,created_at,payload))",
        "genesis": GENESIS,
        "head_hash": res.head_hash,
        "verified": res.ok,
        "events": [
            {"seq": e.seq, "type": e.type, "created_at": e.created_at, "payload": e.payload,
             "prev_hash": e.prev_hash, "hash": e.hash}
            for e in events
        ],
    }


def verify_proof(proof: dict) -> bool:
    prev = proof.get("genesis", GENESIS)
    for e in proof["events"]:
        if e["prev_hash"] != prev:
            return False
        if compute_hash(prev, proof["session_id"], e["seq"], e["type"], e["created_at"], e["payload"]) != e["hash"]:
            return False
        prev = e["hash"]
    return prev == proof["head_hash"]