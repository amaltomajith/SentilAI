"""Forensic PDF carrying a verifiable integrity proof (hash chain head + per-event hashes)."""
from __future__ import annotations

from fpdf import FPDF
from sqlalchemy import select

from sentinel import ledger
from sentinel.db.models import Canary, CanaryHit, Ioc, Session, Takedown, Turn


def _t(s) -> str:
    return str(s if s is not None else "").encode("latin-1", "replace").decode("latin-1")


def mc(pdf, h, txt):
    pdf.multi_cell(0, h, txt, new_x="LMARGIN", new_y="NEXT")


def build_pdf(db, session_id: str) -> bytes:
    s = db.get(Session, session_id)
    proof = ledger.export_proof(db, session_id)
    turns = db.scalars(select(Turn).where(Turn.session_id == session_id).order_by(Turn.seq)).all()
    iocs = db.scalars(select(Ioc).where(Ioc.session_id == session_id)).all()
    hits = db.execute(select(CanaryHit).join(Canary, Canary.token == CanaryHit.token).where(Canary.session_id == session_id)).scalars().all()
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Sentinel - Forensic Session Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    mc(pdf, 5, _t(f"Session: {session_id}\nKind/channel: {s.kind}/{s.channel}   Status: {s.status}   Created: {s.created_at}"))
    pdf.ln(2)
    pdf.set_fill_color(235, 245, 235 if proof["verified"] else 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, _t(f"Integrity: {'VERIFIED' if proof['verified'] else 'FAILED'}  ({len(proof['events'])} chained events)"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 8)
    mc(pdf, 4, _t(f"Chain head (SHA-256): {proof['head_hash']}\nAlgorithm: {proof['algorithm']}\n"
                            "Verify offline: export the proof JSON (GET /api/sessions/<id>/proof.json) and run\n"
                            "  python -m sentinel.verify proof.json"))
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Verified indicators of compromise ({len(iocs)})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for i in iocs:
        extra = ", ".join(f"{k}={v}" for k, v in (i.enrichment or {}).items() if k in ("psp_app", "issuing_bank", "bank", "branch", "city", "registrar") and v)
        mc(pdf, 5, _t(f"[{i.kind}] {i.value}   {extra}   (ledger {i.event_hash[:12]})"))
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    human = [h for h in hits if h.classification == "human"]
    pdf.cell(0, 8, f"Canary telemetry: {len(human)} human open(s), {len(hits) - len(human)} crawler fetch(es) ignored", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for h in human:
        mc(pdf, 5, _t(f"{h.created_at}  ip={h.ip} subnet={h.subnet} isp={h.isp} asn={h.asn}  fp={h.fingerprint_hash[:16]}  {h.fingerprint}"))
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Conversation", new_x="LMARGIN", new_y="NEXT")
    for t in turns:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _t(f"#{t.seq} {t.role.upper()}  {t.created_at}  [{t.event_hash[:12]}]"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        mc(pdf, 5, _t(t.text))
        if t.original_text:
            mc(pdf, 5, _t(f"(original voice transcript: {t.original_text})"))
        if t.role == "agent" and t.gate:
            pdf.set_font("Helvetica", "I", 8)
            mc(pdf, 4, _t(f"gate: {t.gate.get('verdict')}  violations={[v['code'] for v in t.gate.get('violations', [])]}  latency={t.latency_ms}ms"))
        pdf.ln(1)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Appendix - full hash chain", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 7)
    for e in proof["events"]:
        pdf.cell(0, 3.6, _t(f"{e['seq']:>4} {e['type']:<11} {e['hash']}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())