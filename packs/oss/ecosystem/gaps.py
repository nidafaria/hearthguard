"""Task 4: visibility gaps on ecosystem_xz, from the §7.5 query, run as written.

The query text below is copied from docs/HEARTHGUARD.md §7.5; the only addition is the LIMIT cap
that the read-path guard requires (CLAUDE.md). The gap label comes
from the query's CASE expression; nothing here assigns UNREACHABLE or UNNOTICED. Rows where the
role did watch the place and the decision did reference the signal come back with a null gap: they
are counted as covered, not reported as gaps.

A decision is NOT COMPUTED when no role is recorded as watching the place it was made in, or when
the query returns no earlier signal about the identity. The reason is written next to it.
"""

import time
from datetime import UTC, datetime

from core.graph.client import FalkorClient, require_timeout
from core.graph.ro_guard import check_read_only
from packs.oss.ecosystem import graph as G
from packs.oss.ecosystem import parse as P

GAP_QUERY = """\
MATCH (d:Decision {ref:$decision})-[:MADE_IN]->(dp:Place)<-[:WATCHES]-(r:Role)
MATCH (d)-[:CONCERNS]->(i:Identity)-[:SAME_AS*0..2]-(j:Identity)
MATCH (j)-[:EMITTED]->(s:Signal)-[:RECORDED_IN]->(sp:Place)
WHERE s.at < d.at
OPTIONAL MATCH (r)-[w:WATCHES]->(sp) WHERE w.since < s.at
OPTIONAL MATCH (d)-[ref:REFERENCES]->(s)
RETURN s.kind, s.ref, sp.ref AS seen_in,
       CASE WHEN w IS NULL THEN 'UNREACHABLE'
            WHEN ref IS NULL THEN 'UNNOTICED' END AS gap
LIMIT 1000"""

QUERY_TIMEOUT_MS = 10_000


def _ro(client: FalkorClient, graph: str, cypher: str, params: dict):
    check_read_only(cypher)
    return client.graph(graph).ro_query(cypher, params, timeout=require_timeout(QUERY_TIMEOUT_MS))


def _scalar(client: FalkorClient, graph: str, cypher: str, params: dict):
    rs = _ro(client, graph, cypher, params).result_set
    return rs[0][0] if rs else None


def run_decision(client: FalkorClient, graph: str, d: dict, events_by_id: dict) -> dict:
    out = {
        "decision": d["ref"],
        "decision_kind": d["kind"],
        "decision_at": P._iso(d["at"]),
        "place": d["place"],
        "deciding_role": d["deciding_role"],
        "decision_source_url": d["source_url"],
        "query": GAP_QUERY,
    }
    role_rows = _ro(
        client,
        graph,
        "MATCH (d:Decision {ref:$decision})-[:MADE_IN]->(dp:Place)<-[w:WATCHES]-(r:Role) "
        "RETURN r.name, w.since, w.evidence_ref LIMIT 100",
        {"decision": d["ref"]},
    ).result_set
    if not role_rows:
        out.update(
            status="NOT COMPUTED",
            reason=f"no role is recorded as watching {d['place']} in the loaded records",
            gaps=[],
        )
        return out
    out["role_data"] = [
        {
            "role": r,
            "watches_since": P._iso(s),
            "evidence_event": ev,
            "evidenced_before_decision": s < d["at"],
        }
        for r, s, ev in role_rows
    ]
    started = time.perf_counter()
    ran_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = _ro(client, graph, GAP_QUERY, {"decision": d["ref"]})
    out["query_run_at_utc"] = ran_at
    out["query_wall_ms"] = round((time.perf_counter() - started) * 1000, 1)
    out["query_server_ms"] = res.run_time_ms

    seen: dict[str, tuple] = {}
    for kind, sref, place, gap in res.result_set:
        seen[sref] = (kind, place, gap)
    if not seen:
        out.update(
            status="NOT COMPUTED",
            reason="the query returned no earlier signal about this identity in the loaded records",
            gaps=[],
        )
        return out

    gaps, covered = [], 0
    for sref, (kind, place, gap) in sorted(seen.items(), key=lambda kv: events_by_id[kv[0]]["at"]):
        if gap is None:
            covered += 1
            continue
        ev = events_by_id[sref]
        # Which role-in-place evidence the label rests on, so a close call can be seen as one.
        first_seen = _scalar(
            client,
            graph,
            "MATCH (r:Role {name:$role})-[w:WATCHES]->(:Place {ref:$place}) RETURN w.since LIMIT 1",
            {"role": d["deciding_role"], "place": place},
        )
        link = _ro(
            client,
            graph,
            "MATCH (d:Decision {ref:$decision})-[:CONCERNS]->(i:Identity)"
            "-[:SAME_AS*0..2]-(j:Identity)-[:EMITTED]->(:Signal {ref:$sref}) "
            "OPTIONAL MATCH (i)-[x:SAME_AS]-(j) "
            "RETURN i.hid = j.hid, x.evidence, x.strength LIMIT 10",
            {"decision": d["ref"], "sref": sref},
        ).result_set
        same = bool(link and link[0][0])
        via = None if same or not link else {"evidence": link[0][1], "strength": link[0][2]}
        row = {
            "gap": gap,
            "signal": sref,
            "signal_kind": kind,
            "signal_at": ev["at"],
            "signal_place": place,
            "signal_actor_role": ev["actor_role"],
            "signal_source_url": ev["source_url"],
            "decision": d["ref"],
            "decision_source_url": d["source_url"],
            "identity_link": "same identity" if same else via,
            "role_first_evidenced_in_place": P._iso(first_seen) if first_seen is not None else None,
        }
        if first_seen is not None:
            lag = first_seen - _iso_epoch(ev["at"])
            row["seconds_between_role_evidence_and_signal"] = lag
            # The role is first seen in this place within a day after the signal: a close call.
            row["close_call"] = gap == "UNREACHABLE" and 0 < lag <= 86400
        gaps.append(row)
    out.update(
        status="COMPUTED",
        reason=None,
        gaps=gaps,
        signals_checked=len(seen),
        covered_watched_and_referenced=covered,
        unreachable=sum(1 for g in gaps if g["gap"] == "UNREACHABLE"),
        unnoticed=sum(1 for g in gaps if g["gap"] == "UNNOTICED"),
    )
    return out


def _iso_epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def run_all(
    client: FalkorClient, events: list[P.Event], reg: P.Registry, graph: str = G.GRAPH
) -> dict:
    plan = G.plan(events, reg)
    by_id = {r["event_id"]: r for r in plan["rows"]}
    results = [run_decision(client, graph, d, by_id) for d in plan["decisions"]]
    computed = [r for r in results if r["status"] == "COMPUTED"]
    return {
        "graph": graph,
        "method": "docs/HEARTHGUARD.md §7.5, query text unchanged; gap labels come from the query",
        "reading_the_labels": (
            "UNREACHABLE: no loaded record shows the deciding role acting in the signal's place "
            "before the signal. This is absence of evidence, not proof the role was not watching. "
            "UNNOTICED: the role is evidenced in the place before the signal, and the decision "
            "does not reference the signal. A decision references the signals of its own record "
            "and of records its request text cites; nothing else."
        ),
        "scope": (
            "Signals come from the cached records only. xz-devel is a place in the graph but has "
            "no signals here. xz-git has only the commits that carry the identity behind the "
            "Debian request. Gaps are therefore a lower bound."
        ),
        "decisions_computed": len(computed),
        "decisions_not_computed": len(results) - len(computed),
        "gap_rows": sum(len(r["gaps"]) for r in results),
        "unreachable_rows": sum(r.get("unreachable", 0) for r in results),
        "unnoticed_rows": sum(r.get("unnoticed", 0) for r in results),
        "decisions": results,
    }
