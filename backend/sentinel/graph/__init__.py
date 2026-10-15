"""Cross-session syndicate attribution ("mule-ring") graph.

Bipartite graph session <-> artifact. Artifacts carry a weight (how strongly sharing it implies the same
operators). Sessions are linked when they share an artifact; connected components of that projection are rings.
IFSC and /24-subnet sharing are deliberately WEAK links (big branches / shared ISPs create coincidences), so a
ring held together only by weak links is reported as low confidence.
"""
from __future__ import annotations

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from sentinel.db.models import CanaryHit, Canary, HoneyToken, Ioc, Session

WEIGHTS = {"upi": 1.0, "bank_account": 1.0, "domain": 0.9, "fingerprint": 0.9, "phone": 0.8, "url": 0.7,
           "ifsc": 0.4, "subnet": 0.3, "asn": 0.1}
STRONG = 0.7


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower()


def session_artifacts(db: DbSession, only: set[str] | None = None) -> dict[str, set[tuple[str, str]]]:
    honey = {h.value.lower() for h in db.scalars(select(HoneyToken))}
    arts: dict[str, set[tuple[str, str]]] = {}

    def add(sid, kind, val):
        if only is not None and sid not in only:
            return
        if val and val.lower() not in honey:
            arts.setdefault(sid, set()).add((kind, val.lower() if kind in ("upi", "domain") else val))

    for i in db.scalars(select(Ioc)):
        add(i.session_id, i.kind, i.value)
        if i.kind == "url":
            add(i.session_id, "domain", _domain(i.value))
    for hit, can in db.execute(select(CanaryHit, Canary).join(Canary, Canary.token == CanaryHit.token)):
        if hit.classification != "human":
            continue  # crawler hits say nothing about the attacker
        add(can.session_id, "subnet", hit.subnet)
        add(can.session_id, "fingerprint", hit.fingerprint_hash)
        if hit.asn:
            add(can.session_id, "asn", hit.asn)
    return arts


def build_graph(db: DbSession, only: set[str] | None = None) -> nx.Graph:
    g = nx.Graph()
    for sid, arts in session_artifacts(db, only).items():
        g.add_node(("session", sid), type="session", label=sid[:8])
        for kind, val in arts:
            node = (kind, val)
            g.add_node(node, type=kind, label=val[:40])
            g.add_edge(("session", sid), node, weight=WEIGHTS.get(kind, 0.1))
    return g


def rings(g: nx.Graph, min_weight: float = 0.3) -> list[dict]:
    """Project to sessions; edge weight = max weight of shared artifacts (noisy-OR over them)."""
    sessions = [n for n in g if n[0] == "session"]
    proj = nx.Graph()
    proj.add_nodes_from(sessions)
    for art in (n for n in g if n[0] != "session"):
        sess = [n for n in g.neighbors(art) if n[0] == "session"]
        w = g.nodes[art].get("type") and WEIGHTS.get(art[0], 0.1)
        for i in range(len(sess)):
            for j in range(i + 1, len(sess)):
                a, b = sess[i], sess[j]
                prev = proj.get_edge_data(a, b, {"shared": [], "p_none": 1.0})
                shared = prev["shared"] + [{"kind": art[0], "value": art[1], "weight": w}]
                proj.add_edge(a, b, shared=shared, p_none=prev["p_none"] * (1 - w), weight=1 - prev["p_none"] * (1 - w))
    strong = nx.Graph()
    strong.add_nodes_from(sessions)
    strong.add_edges_from((u, v, d) for u, v, d in proj.edges(data=True) if d["weight"] >= min_weight)
    out = []
    for comp in nx.connected_components(strong):
        if len(comp) < 2:
            continue
        sub = strong.subgraph(comp)
        edges = list(sub.edges(data=True))
        strong_only = nx.Graph()
        strong_only.add_nodes_from(comp)
        strong_only.add_edges_from((u, v) for u, v, d in edges if any(s["weight"] >= STRONG for s in d["shared"]))
        n_strong = nx.number_connected_components(strong_only)
        confidence = "high" if n_strong == 1 else ("mixed" if strong_only.number_of_edges() else "low")
        shared_kinds = sorted({s["kind"] for _, _, d in edges for s in d["shared"]})
        out.append({
            "sessions": sorted(n[1] for n in comp),
            "size": len(comp),
            "confidence": confidence,
            "score": round(sum(d["weight"] for _, _, d in edges), 2),
            "shared_artifact_kinds": shared_kinds,
            "links": [{"a": u[1], "b": v[1], "weight": round(d["weight"], 2), "shared": d["shared"]} for u, v, d in edges],
        })
    return sorted(out, key=lambda r: (-r["size"], -r["score"]))


def to_node_link(g: nx.Graph, ring_list: list[dict]) -> dict:
    ring_of = {s: i for i, r in enumerate(ring_list) for s in r["sessions"]}
    nodes = [{"id": f"{n[0]}:{n[1]}", "type": d["type"], "label": d["label"],
              "ring": ring_of.get(n[1]) if n[0] == "session" else None} for n, d in g.nodes(data=True)]
    edges = [{"source": f"{u[0]}:{u[1]}", "target": f"{v[0]}:{v[1]}", "weight": d["weight"]} for u, v, d in g.edges(data=True)]
    return {"nodes": nodes, "edges": edges, "rings": ring_list}


def attribution(db: DbSession, user_id: str | None = None) -> dict:
    only = None if user_id is None else set(db.scalars(select(Session.id).where(Session.user_id == user_id)))
    g = build_graph(db, only)
    return to_node_link(g, rings(g))