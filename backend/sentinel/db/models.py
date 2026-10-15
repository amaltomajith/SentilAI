"""Relational schema. Works on SQLite (local/CI) and PostgreSQL (prod): no dialect-specific types."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(16), default="live")  # live | simulation | manual
    channel: Mapped[str] = mapped_column(String(16), default="web")  # web | whatsapp
    peer: Mapped[str] = mapped_column(String(64), default="")  # scammer number / handle (digits)
    status: Mapped[str] = mapped_column(String(24), default="active")  # active | halted_benign | halted_uncertain | closed
    scenario_id: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)  # Clerk subject; "" = unowned (never served by the API)
    pending_tactic: Mapped[str] = mapped_column(String(96), default="")        # "scam_type|tactic" awaiting its outcome on the next inbound
    exchange_count: Mapped[int] = mapped_column(Integer, default=0)
    head_hash: Mapped[str] = mapped_column(String(64), default="0" * 64)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LedgerEvent(Base):
    """Append-only hash chain, one per session. Turns, IOCs, tool traces and canary hits are all events."""
    __tablename__ = "ledger_events"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(24))  # turn | ioc | tool_trace | gate | canary_hit | note
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))  # ISO string; part of the hashed content
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Turn(Base):
    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(12))  # scammer | agent
    text: Mapped[str] = mapped_column(Text)  # final text (what was received / sent)
    original_text: Mapped[str] = mapped_column(Text, default="")  # voice note: original-language transcript
    media_kind: Mapped[str] = mapped_column(String(12), default="text")  # text | voice | image
    draft_text: Mapped[str] = mapped_column(Text, default="")  # agent only: raw model draft
    gate: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    event_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Ioc(Base):
    __tablename__ = "iocs"
    __table_args__ = (UniqueConstraint("session_id", "kind", "value"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), default="")
    kind: Mapped[str] = mapped_column(String(16), index=True)  # upi | phone | url | bank_account | ifsc | domain
    value: Mapped[str] = mapped_column(String(512), index=True)
    enrichment: Mapped[dict] = mapped_column(JSON, default=dict)
    event_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class HoneyToken(Base):
    """Values Sentinel itself invented or handed out. They must never be logged as scammer intel."""
    __tablename__ = "honey_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), default="", index=True)  # "" = global
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(512), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ToolTrace(Base):
    __tablename__ = "tool_traces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    turn_seq: Mapped[int] = mapped_column(Integer, default=0)
    tool: Mapped[str] = mapped_column(String(48))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    ok: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    event_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Canary(Base):
    __tablename__ = "canaries"
    token: Mapped[str] = mapped_column(String(48), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # receipt | kyc
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    hits: Mapped[list["CanaryHit"]] = relationship(back_populates="canary")


class CanaryHit(Base):
    __tablename__ = "canary_hits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token: Mapped[str] = mapped_column(ForeignKey("canaries.token"), index=True)
    classification: Mapped[str] = mapped_column(String(12))  # crawler | human
    ip: Mapped[str] = mapped_column(String(64), default="")
    subnet: Mapped[str] = mapped_column(String(64), default="")
    asn: Mapped[str] = mapped_column(String(64), default="")
    isp: Mapped[str] = mapped_column(String(128), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    canary: Mapped[Canary] = relationship(back_populates="hits")


class Takedown(Base):
    __tablename__ = "takedowns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    target_kind: Mapped[str] = mapped_column(String(16))
    target: Mapped[str] = mapped_column(String(512))
    recipient: Mapped[str] = mapped_column(String(256), default="")
    bundle: Mapped[dict] = mapped_column(JSON, default=dict)  # STIX 2.1
    report: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="drafted")  # drafted | approved | rejected | dispatched
    dispatch_mode: Mapped[str] = mapped_column(String(10), default="dry_run")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BridgeOutbox(Base):
    """Backend-approved outbound jobs. The bridge leases and sends each one exactly once."""
    __tablename__ = "bridge_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    peer: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(8), default="text")  # text | image | voice
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(8), default="pending")  # pending | leased | sent
    inbound_id: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BridgeSeen(Base):
    """Replay protection: nonces and inbound message ids already processed."""
    __tablename__ = "bridge_seen"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    """One row per Clerk subject. Created on first authenticated request."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)   # accepted the responsible-use terms
    collective_opt_in: Mapped[int] = mapped_column(Integer, default=0)                              # share anonymised tactic counters
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Profile(Base):
    """What the user tells the agent about themselves. `data` holds fields, `share` marks which may be revealed to a scammer."""
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    share: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TargetNumber(Base):
    """Numbers a user authorised Sentinel to engage on THEIR WhatsApp. Everything else is ignored."""
    __tablename__ = "target_numbers"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TacticStat(Base):
    """Outcome counters for the adaptive tactic chooser. scope = a user id (private) or '*' (opt-in, anonymised, counters only)."""
    __tablename__ = "tactic_stats"
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    scam_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    tactic: Mapped[str] = mapped_column(String(48), primary_key=True)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    trials: Mapped[int] = mapped_column(Integer, default=0)
