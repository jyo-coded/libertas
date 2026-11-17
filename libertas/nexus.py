"""Nexus: the correlation graph (blueprint §13.4).

Nodes: source, account, actor, item, org, wallet, cluster, entity, indicator, incident.
Every edge carries the relation and, where inferred, its confidence and truth level, so the shortest
evidence path between two nodes can be read out as an explanation.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import networkx as nx

from .common.timeutil import now_iso, parse_iso
from .stilus import UnionFind

SENSITIVE = ("aadhaar", "mobile_in", "email", "upi", "pan")
OPERATIONAL = ("pgp_fingerprint", "tox_id", "session_id", "jabber", "telegram")
INCIDENT_WINDOW = timedelta(days=30)


class Nexus:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ---------- incidents ----------
    def recompute_incidents(self) -> list[dict]:
        """An incident groups posts about the SAME organisation (single-subject posts only, within 30 days) plus
        posts carrying the SAME sample data. The same data under different organisation names is kept as a
        cross-reference, not merged, because the claimed victim is then itself in doubt."""
        uf = UnionFind()
        rows = self.conn.execute(
            "SELECT i.id, i.first_seen, i.source_id, i.title, i.deleted_at, a.orgs_json, a.categories_json, "
            "(SELECT COUNT(*) FROM alerts al WHERE al.item_id=i.id) AS alerted FROM items i "
            "JOIN assessments a ON a.item_id=i.id ORDER BY i.first_seen").fetchall()
        info = {r["id"]: r for r in rows}
        org_of = {r["id"]: {o["org"] for o in json.loads(r["orgs_json"] or "[]")} for r in rows}
        shared: dict[tuple[int, int], int] = {}
        cross: list[dict] = []
        for r in self.conn.execute(
                f"SELECT a.item_id AS x, b.item_id AS y, COUNT(*) AS n FROM indicators a JOIN indicators b ON a.kind=b.kind "
                f"AND a.value=b.value AND a.item_id < b.item_id WHERE a.kind IN {SENSITIVE} GROUP BY a.item_id, b.item_id "
                f"HAVING n >= 2"):
            ox, oy = org_of.get(r["x"], set()), org_of.get(r["y"], set())
            if ox and oy and not (ox & oy):
                cross.append({"items": [r["x"], r["y"]], "shared_identifiers": r["n"],
                              "note": "same sample data under different organisation names"})
                continue
            uf.union(r["x"], r["y"])
            shared[(r["x"], r["y"])] = r["n"]
        by_org: dict[str, list] = {}
        for r in rows:
            uf.find(r["id"])
            orgs = org_of[r["id"]]
            if r["alerted"] and len(orgs) == 1:
                by_org.setdefault(next(iter(orgs)), []).append(r)
        for org_items in by_org.values():
            for prev, cur in zip(org_items, org_items[1:]):
                t1, t2 = parse_iso(prev["first_seen"]), parse_iso(cur["first_seen"])
                if t1 and t2 and t2 - t1 <= INCIDENT_WINDOW:
                    uf.union(prev["id"], cur["id"])
        ts, live = now_iso(), set()
        incidents = []
        for group in uf.groups():
            members = sorted((i for i in group if i in info), key=lambda i: info[i]["first_seen"])
            if len(members) < 2 or not any(info[i]["alerted"] for i in members):
                continue
            orgs = sorted({o["org"] for i in members for o in json.loads(info[i]["orgs_json"] or "[]")})
            sources = sorted({info[i]["source_id"] for i in members})
            key = f"incident:{members[0]}"
            timeline = [{"item_id": i, "first_seen": info[i]["first_seen"], "source": info[i]["source_id"],
                         "title": info[i]["title"], "deleted": bool(info[i]["deleted_at"]),
                         "category": (json.loads(info[i]["categories_json"] or "[]") or [{}])[0].get("label")}
                        for i in members]
            datasets = [{"items": [x, y], "shared_identifiers": n} for (x, y), n in shared.items() if x in group and y in group]
            datasets += [c for c in cross if set(c["items"]) & set(members)]
            title = f"{', '.join(orgs) or 'Unattributed'}: {len(members)} posts across {len(sources)} site(s)"
            self.conn.execute(
                "INSERT INTO incidents(key, title, org, first_seen, last_seen, item_ids_json, sources_json, summary_json, "
                "updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET title=excluded.title, "
                "org=excluded.org, last_seen=excluded.last_seen, item_ids_json=excluded.item_ids_json, "
                "sources_json=excluded.sources_json, summary_json=excluded.summary_json, updated_at=excluded.updated_at",
                (key, title, ", ".join(orgs), timeline[0]["first_seen"], timeline[-1]["first_seen"], json.dumps(members),
                 json.dumps(sources), json.dumps({"timeline": timeline, "shared_datasets": datasets}), ts))
            live.add(key)
            incidents.append({"key": key, "title": title, "items": members})
        for row in self.conn.execute("SELECT key FROM incidents").fetchall():
            if row["key"] not in live:
                self.conn.execute("DELETE FROM incidents WHERE key=?", (row["key"],))
        return incidents

    # ---------- graph ----------
    def graph(self) -> nx.MultiGraph:
        g = nx.MultiGraph()
        for s in self.conn.execute("SELECT id, name FROM sources"):
            g.add_node(f"source:{s['id']}", type="source", label=s["name"])
        accounts = {}
        for a in self.conn.execute("SELECT id, source_id, alias, actor_id FROM accounts"):
            node = f"account:{a['id']}"
            accounts[(a["source_id"], a["alias"])] = node
            g.add_node(node, type="account", label=a["alias"], source=a["source_id"])
            g.add_edge(node, f"source:{a['source_id']}", relation="active on")
        for ac in self.conn.execute("SELECT * FROM actors"):
            node = f"actor:{ac['id']}"
            g.add_node(node, type="actor", label=f"Actor: {ac['label']}", truth=ac["truth"])
            for m in json.loads(ac["members_json"]):
                g.add_edge(f"account:{m['account_id']}", node, relation="attributed to (lead)",
                           probability=m["best_link"], truth=ac["truth"])
        for l in self.conn.execute("SELECT * FROM account_links"):
            kinds = sorted({e.get("kind") or e["family"] for e in json.loads(l["evidence_json"])})
            g.add_edge(f"account:{l['a']}", f"account:{l['b']}", relation="linked: " + ", ".join(kinds),
                       probability=l["probability"], truth=l["truth"])
        sev = {r["item_id"]: (r["severity"], r["score"]) for r in self.conn.execute("SELECT item_id, severity, score FROM alerts")}
        for it in self.conn.execute("SELECT i.id, i.source_id, i.author, i.title, i.kind, i.deleted_at, i.first_seen, "
                                    "a.orgs_json FROM items i LEFT JOIN assessments a ON a.item_id=i.id"):
            node = f"item:{it['id']}"
            severity, score = sev.get(it["id"], (None, None))
            g.add_node(node, type="item", label=(it["title"] or "")[:80], kind=it["kind"], severity=severity, score=score,
                       deleted=bool(it["deleted_at"]), first_seen=it["first_seen"])
            acc = accounts.get((it["source_id"], it["author"]))
            g.add_edge(acc or f"source:{it['source_id']}", node, relation="posted" if acc else "hosted")
            for o in json.loads(it["orgs_json"] or "[]"):
                g.add_node(f"org:{o['org']}", type="org", label=o["org"], sector=o["sector"], city=o.get("city"))
                g.add_edge(node, f"org:{o['org']}", relation="mentions")
        for ind in self.conn.execute(f"SELECT item_id, kind, value, display FROM indicators WHERE kind IN {OPERATIONAL} "
                                     f"OR kind LIKE 'wallet_%'"):
            node = f"wallet:{ind['value']}" if ind["kind"].startswith("wallet_") else f"ind:{ind['kind']}:{ind['value']}"
            g.add_node(node, type="wallet" if ind["kind"].startswith("wallet_") else "indicator",
                       label=ind["display"][:40], kind=ind["kind"])
            g.add_edge(f"item:{ind['item_id']}", node, relation="contains")
        for w in self.conn.execute("SELECT address, cluster_id FROM wallets WHERE cluster_id IS NOT NULL"):
            g.add_edge(f"wallet:{w['address']}", f"cluster:{w['cluster_id']}", relation="in cluster (heuristic)")
        for c in self.conn.execute("SELECT id, size, exposure_json, flags_json FROM wallet_clusters"):
            node = f"cluster:{c['id']}"
            g.add_node(node, type="cluster", label=f"{c['id']} ({c['size']} addresses)")
            for e in json.loads(c["exposure_json"] or "[]"):
                ent = f"entity:{e['entity']}"
                g.add_node(ent, type="entity", label=e["entity"])
                g.add_edge(node, ent, relation=f"sent {e['btc']} BTC to")
        for inc in self.conn.execute("SELECT id, title, item_ids_json FROM incidents"):
            node = f"incident:{inc['id']}"
            g.add_node(node, type="incident", label=inc["title"])
            for i in json.loads(inc["item_ids_json"]):
                g.add_edge(f"item:{i}", node, relation="part of")
        return g

    def subgraph(self, focus: str, depth: int = 2, limit: int = 300) -> dict:
        g = self.graph()
        if focus not in g:
            return {"nodes": [], "edges": [], "focus": focus, "error": "unknown node"}
        simple = nx.Graph(g)
        keep = list(nx.ego_graph(simple, focus, radius=depth).nodes)[:limit]
        sub = g.subgraph(keep)
        return {"focus": focus,
                "nodes": [{"id": n, **d} for n, d in sub.nodes(data=True)],
                "edges": [{"source": u, "target": v, **d} for u, v, d in sub.edges(data=True)]}

    def evidence_path(self, a: str, b: str) -> list[dict]:
        g = self.graph()
        if a not in g or b not in g:
            return []
        try:
            path = nx.shortest_path(nx.Graph(g), a, b)
        except nx.NetworkXNoPath:
            return []
        steps = []
        for u, v in zip(path, path[1:]):
            data = min(g.get_edge_data(u, v).values(), key=lambda d: -(d.get("probability") or 1))
            steps.append({"from": u, "from_label": g.nodes[u].get("label"), "to": v, "to_label": g.nodes[v].get("label"),
                          **data})
        return steps

    # ---------- per-item correlation ----------
    def correlate(self, item_id: int, attribution: dict | None) -> dict:
        out: dict = {"wallet_links": [], "incident": None, "escalation": None}
        for w in self.conn.execute("SELECT DISTINCT ind.value, wl.cluster_id FROM indicators ind LEFT JOIN wallets wl "
                                   "ON wl.address=ind.value WHERE ind.item_id=? AND ind.kind='wallet_btc'", (item_id,)):
            if not w["cluster_id"]:
                continue
            others = self.conn.execute(
                "SELECT DISTINCT i.id, i.title, s.name AS source_name, i.author, ind.value FROM indicators ind JOIN wallets wl "
                "ON wl.address=ind.value JOIN items i ON i.id=ind.item_id JOIN sources s ON s.id=i.source_id "
                "WHERE wl.cluster_id=? AND ind.item_id != ? AND ind.kind='wallet_btc' ORDER BY i.first_seen",
                (w["cluster_id"], item_id)).fetchall()
            if others:
                out["wallet_links"].append({"wallet": w["value"], "cluster": w["cluster_id"],
                                            "same_wallet": sum(1 for o in others if o["value"] == w["value"]),
                                            "items": [{"id": o["id"], "title": o["title"], "source": o["source_name"],
                                                       "author": o["author"], "same_wallet": o["value"] == w["value"]}
                                                      for o in others]})
        for inc in self.conn.execute("SELECT * FROM incidents"):
            if item_id in json.loads(inc["item_ids_json"]):
                out["incident"] = {"id": inc["id"], "title": inc["title"],
                                   "items": len(json.loads(inc["item_ids_json"])),
                                   "sources": json.loads(inc["sources_json"])}
                break
        a = self.conn.execute("SELECT orgs_json FROM assessments WHERE item_id=?", (item_id,)).fetchone()
        orgs = {o["org"] for o in json.loads(a["orgs_json"] or "[]")} if a else set()
        actor = (attribution or {}).get("actor")
        if actor and orgs and actor["prior_items"]:
            new = sorted(orgs - set(actor["prior_targets"]))
            if new:
                out["escalation"] = {"actor": actor["label"], "new_targets": new, "previous_targets": actor["prior_targets"]}
        return out
