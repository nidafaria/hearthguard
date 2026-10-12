"""Task 3: build `ecosystem_xz` in FalkorDB from the parsed events (docs/HEARTHGUARD.md §6.2).

Every write is a MERGE on a unique key, so loading again changes no count.

Nodes:  Place (6), Identity (hashed ids only), Role, Signal (one per event), Decision (4).
Edges:  ACTIVE_IN {first_at, last_at, actions}, EMITTED, RECORDED_IN, SAME_AS, WATCHES {since},
        MADE_IN, CONCERNS, REFERENCES.

Modelling choices that decide the gap result, so they are stated here and repeated in the output:
  - WATCHES exists only for a decision-making role, in a place where a holder of that role is seen
    acting in the loaded records, and `since` is the earliest such action. So "UNREACHABLE" means
    "no record shows this role in that place before the signal", not "proved it was not watching".
  - A decision REFERENCES the signals of its own record (the request it decides) dated at or
    before the decision, and likewise for any record its request text cites. Nothing else.
  - SAME_AS links two identities only by display-name hash (`persona_name`, strength 0.5). An
    email-hash or handle match makes them one Identity, not an edge.
"""

from collections import defaultdict
from dataclasses import dataclass

from core.graph.client import FalkorClient
from core.graph.schema import list_constraints
from packs.oss.ecosystem import parse as P

GRAPH = "ecosystem_xz"
WRITE_TIMEOUT_MS = 30_000
READ_TIMEOUT_MS = 10_000

UNIQUE = (
    ("Place", "ref"),
    ("Identity", "hid"),
    ("Role", "name"),
    ("Signal", "ref"),
    ("Decision", "ref"),
)


@dataclass
class DecisionDef:
    ref: str
    kind: str
    record: str
    place: str
    deciding_role: str
    request_kind: str  # the event that is the request being decided
    at_kind: str  # the event whose time is the decision time
    concerns_kind: str  # the event whose actor the decision is about


DECISIONS = [
    DecisionDef(
        "oss-fuzz-build-change-pr10667",
        "merge_build_change",
        "oss-fuzz PR 10667",
        "oss-fuzz",
        P.ROLE_OSSFUZZ,
        "pr_opened",
        "pr_merged",
        "pr_opened",
    ),
    DecisionDef(
        "kernel-maintainer-entry-lkml-2024-3-20-1008",
        "add_maintainer_entry",
        "lkml 2024/3/20/1008",
        "lkml",
        P.ROLE_KERNEL,
        "patch_sent",
        "patch_sent",
        "reviewed_by_tag",
    ),
    DecisionDef(
        "debian-upgrade-request-bug1067708",
        "accept_upgrade",
        "debian bug 1067708",
        "debian-bts",
        P.ROLE_DEB_MAINT,
        "bug_filed",
        "bug_filed",
        "bug_filed",
    ),
    DecisionDef(
        "launchpad-upgrade-request-bug2059417",
        "accept_upgrade",
        "launchpad bug 2059417",
        "launchpad",
        P.ROLE_UBUNTU,
        "bug_filed",
        "bug_filed",
        "bug_filed",
    ),
]


def ensure_schema(client: FalkorClient, graph: str = GRAPH) -> None:
    have = (
        {(c["label"], tuple(c["properties"])) for c in list_constraints(client, graph)}
        if graph in _graph_names(client)
        else set()
    )
    for label, prop in UNIQUE:
        if (label, (prop,)) in have:
            continue
        client.query(graph, f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        client.db.execute_command(
            "GRAPH.CONSTRAINT", "CREATE", graph, "UNIQUE", "NODE", label, "PROPERTIES", "1", prop
        )
    for label, prop in (("Signal", "at"), ("Decision", "at")):
        try:
            client.query(graph, f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception as e:  # an existing index is fine
            if "already" not in str(e).lower() and "index" not in str(e).lower():
                raise


def _graph_names(client: FalkorClient) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


def plan(events: list[P.Event], reg: P.Registry) -> dict:
    """Everything that will be written, as plain rows. Pure: no database access."""
    rows = P.event_rows(events, reg)
    by_id = {r["event_id"]: r for r in rows}
    epochs = {e.event_id: e.at for e in events}

    ident: dict[str, dict] = {}
    for e in events:
        hid = reg.hid(e.obs)
        root = reg.find(reg.keys_of(e.obs)[0])
        names = reg.names.get(root, set())
        item = ident.setdefault(
            hid,
            {
                "hid": hid,
                "persona": None,
                "handles": set(),
                "first": e.at,
                "last": e.at,
                "name_hashes": {reg.name_hash(n) for n in names},
            },
        )
        if P.PERSONA in names:
            item["persona"] = P.PERSONA
            item["handles"] |= {h for _, h in reg.handles.get(root, set())}
        item["first"], item["last"] = min(item["first"], e.at), max(item["last"], e.at)

    active: dict[tuple[str, str], dict] = {}
    for e in events:
        k = (reg.hid(e.obs), e.place)
        a = active.setdefault(k, {"first": e.at, "last": e.at, "actions": 0})
        a["first"], a["last"], a["actions"] = (
            min(a["first"], e.at),
            max(a["last"], e.at),
            a["actions"] + 1,
        )

    deciding = {d.deciding_role for d in DECISIONS}
    watches: dict[tuple[str, str], dict] = {}
    for e in events:
        if e.role in deciding:
            k = (e.role, e.place)
            if k not in watches or e.at < watches[k]["since"]:
                watches[k] = {"since": e.at, "evidence": e.event_id}

    by_name: dict[str, set[str]] = defaultdict(set)
    for hid, it in ident.items():
        for nh in it["name_hashes"]:
            by_name[nh].add(hid)
    same_as = sorted({(a, b) for hs in by_name.values() for a in hs for b in hs if a < b})

    decisions = []
    for d in DECISIONS:
        own = [e for e in events if e.record == d.record]
        at_ev = next(e for e in own if e.kind == d.at_kind)
        con_ev = next(e for e in own if e.kind == d.concerns_kind)
        req = next(e for e in own if e.kind == d.request_kind)
        refs = [(e.event_id, "same_record") for e in own if e.at <= at_ev.at]
        for rec in req.refs_records:
            refs += [
                (e.event_id, "cited_in_text")
                for e in events
                if e.record == rec and e.at <= at_ev.at
            ]
        decisions.append(
            {
                "ref": d.ref,
                "kind": d.kind,
                "at": at_ev.at,
                "record": d.record,
                "place": d.place,
                "deciding_role": d.deciding_role,
                "concerns": reg.hid(con_ev.obs),
                "source_url": by_id[at_ev.event_id]["source_url"],
                "references": refs,
            }
        )
    return {
        "rows": rows,
        "epochs": epochs,
        "identities": list(ident.values()),
        "active_in": active,
        "watches": watches,
        "same_as": same_as,
        "decisions": decisions,
    }


def load(client: FalkorClient, events: list[P.Event], reg: P.Registry, graph: str = GRAPH) -> None:
    ensure_schema(client, graph)
    p = plan(events, reg)

    def _q(client: FalkorClient, cypher: str, params: dict | None = None):
        return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    for ref, kind in P.PLACES.items():
        _q(client, "MERGE (p:Place {ref: $ref}) SET p.kind = $kind", {"ref": ref, "kind": kind})
    for it in p["identities"]:
        _q(
            client,
            "MERGE (i:Identity {hid: $hid}) SET i.first_at = $first, i.last_at = $last, "
            "i.persona_public = $persona, i.handles_public = $handles",
            {
                "hid": it["hid"],
                "first": it["first"],
                "last": it["last"],
                "persona": it["persona"],
                "handles": sorted(it["handles"]) if it["persona"] else [],
            },
        )
    for r in p["rows"]:
        _q(
            client,
            "MERGE (s:Signal {ref: $ref}) "
            "SET s.kind = $kind, s.at = $at, s.at_iso = $at_iso, s.source_url = $url, "
            "s.record = $record, s.actor_role = $role, s.action = $action "
            "WITH s MATCH (i:Identity {hid: $hid}), (pl:Place {ref: $place}) "
            "MERGE (i)-[:EMITTED]->(s) MERGE (s)-[:RECORDED_IN]->(pl)",
            {
                "ref": r["event_id"],
                "kind": r["kind"],
                "at": p["epochs"][r["event_id"]],
                "at_iso": r["at"],
                "url": r["source_url"],
                "record": r["record"],
                "role": r["actor_role"],
                "action": r["action"],
                "hid": r["actor_hid"],
                "place": r["place"],
            },
        )
    for (hid, place), a in p["active_in"].items():
        _q(
            client,
            "MATCH (i:Identity {hid: $hid}), (pl:Place {ref: $place}) "
            "MERGE (i)-[a:ACTIVE_IN]->(pl) SET a.first_at = $f, a.last_at = $l, a.actions = $n",
            {"hid": hid, "place": place, "f": a["first"], "l": a["last"], "n": a["actions"]},
        )
    for a, b in p["same_as"]:
        _q(
            client,
            "MATCH (x:Identity {hid: $a}), (y:Identity {hid: $b}) "
            "MERGE (x)-[s:SAME_AS]->(y) SET s.evidence = 'persona_name', s.strength = 0.5",
            {"a": a, "b": b},
        )
    for (role, place), w in p["watches"].items():
        _q(
            client,
            "MERGE (r:Role {name: $role}) WITH r MATCH (pl:Place {ref: $place}) "
            "MERGE (r)-[w:WATCHES]->(pl) SET w.since = $since, w.evidence_ref = $ev",
            {"role": role, "place": place, "since": w["since"], "ev": w["evidence"]},
        )
    for d in p["decisions"]:
        _q(
            client,
            "MERGE (d:Decision {ref: $ref}) "
            "SET d.kind = $kind, d.at = $at, d.at_iso = $at_iso, d.record = $record, "
            "d.deciding_role = $role, d.source_url = $url "
            "WITH d MATCH (pl:Place {ref: $place}), (i:Identity {hid: $concerns}) "
            "MERGE (d)-[:MADE_IN]->(pl) MERGE (d)-[:CONCERNS]->(i)",
            {
                "ref": d["ref"],
                "kind": d["kind"],
                "at": d["at"],
                "at_iso": P._iso(d["at"]),
                "record": d["record"],
                "role": d["deciding_role"],
                "url": d["source_url"],
                "place": d["place"],
                "concerns": d["concerns"],
            },
        )
        for sref, basis in d["references"]:
            _q(
                client,
                "MATCH (d:Decision {ref: $d}), (s:Signal {ref: $s}) "
                "MERGE (d)-[r:REFERENCES]->(s) SET r.basis = $basis",
                {"d": d["ref"], "s": sref, "basis": basis},
            )


def counts(client: FalkorClient, graph: str = GRAPH) -> dict:
    nodes = {
        row[0]: row[1]
        for row in client.query(
            graph,
            "MATCH (n) RETURN labels(n)[0], count(n) ORDER BY labels(n)[0]",
            timeout_ms=READ_TIMEOUT_MS,
        ).result_set
    }
    edges = {
        row[0]: row[1]
        for row in client.query(
            graph,
            "MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY type(r)",
            timeout_ms=READ_TIMEOUT_MS,
        ).result_set
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "node_total": sum(nodes.values()),
        "edge_total": sum(edges.values()),
    }
