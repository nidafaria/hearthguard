"""hearthguard-core tool logic (spec §12.1): nine read-only questions about an org's trust graph.

  check_trust(org, actor, action)      is this actor young, vouched for, and on a path to `action`?
  takeover_cost(org, privilege)        the fewest approvals an outsider must win (SPpaths)
  guardians(org, privilege)            the fewest people on every route from an outsider (maxFlow)
  org_normal(org)                      the remembered normal metrics (Normal nodes)
  trust_path(org, actor, privilege)    the shortest trust path from an actor to a privilege
  visibility_gaps(decision)            who could have seen what before a downstream decision
  simulate_hardening(org, step)        one menu step on a COPY of the graph, before and after
  why(finding_id)                      a finding, its evidence, each quote and its source link
  claims_for(actor, window)            the claims an actor made in the last `window` days

Rules (spec §8.4, §9, §12.1):
  - No tool writes to the org graph. simulate_hardening copies the org graph to a scratch name,
    changes the copy and drops it, as core/hardening/simulate.py does.
  - Every read takes an as-of time T. When none is given, T is the time of the newest event in the
    graph, and the result says `T_defaulted: true`.
  - Every query goes through the read-only guard with an explicit timeout and a LIMIT.
  - No LLM. The Liaison's send path is NOT here: nothing in this server sends anything.
  - `actor` is an identifier. A raw identifier is hashed with the org salt before it is looked up;
    a value that already looks like a hid (64 hex characters) is used as is. Hashed ids come back,
    never a raw identifier.
Statuses are never hidden: a computation that could not run says NOT COMPUTED and why.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from core.agents import why as why_mod
from core.agents.cases import CASES
from core.detectors import low_history as lh
from core.detectors import pressure, vouch
from core.graph.as_of import run_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.hashing import identifier_hash
from core.graph.ro_guard import ro_query
from core.hardening import simulate as sim
from core.takeover import cost, guardians, trust_path
from core.takeover import scratch as sc

ROOT = Path(__file__).resolve().parents[2]
GAPS_FILE = ROOT / "eval" / "results" / "ecosystem_gaps.json"
DAY_S = 86_400
HID = re.compile(r"^[0-9a-f]{64}$")

NEWEST_QUERY = (
    "MATCH (x:Action) WITH max(x.at) AS a "
    "OPTIONAL MATCH (c:Claim) WITH a, max(c.at) AS b "
    "OPTIONAL MATCH ()-[g:GRANTED]->() RETURN a, b, max(g.at) AS c LIMIT 1"
)
NORMAL_QUERY = (
    "MATCH (n:Normal) WHERE n.computed_at <= $T "
    "RETURN n.metric AS metric, n.scope AS scope, n.window AS window, "
    "n.computed_at AS computed_at, n.value AS value "
    "ORDER BY metric, scope, window, computed_at DESC LIMIT 1000"
)
CLAIMS_QUERY = (
    "MATCH (a:Actor {hid: $hid})-[:ASSERTED]->(c:Claim) "
    "WHERE c.at <= $T AND c.at > $since "
    "OPTIONAL MATCH (c)-[:FROM]->(s:Span)<-[:HAS]-(src:Source) "
    "RETURN c.id AS claim_id, c.kind AS kind, c.at AS at, c.target_hid AS target, "
    "s.text AS quote, src.url AS link, src.ref AS ref, src.type AS source_type "
    "ORDER BY at, claim_id LIMIT 200"
)
VOUCHED_BY_QUERY = (
    "MATCH (v:Actor)-[:ASSERTED]->(c:Claim {kind: 'VOUCH', target_hid: $hid}) WHERE c.at <= $T "
    "RETURN DISTINCT v.hid AS voucher ORDER BY voucher LIMIT 200"
)
HOLDS_QUERY = (
    "MATCH (a:Actor {hid: $hid})-[e:GRANTED|CAN_GRANT]->(p:Privilege {kind: $kind}) "
    "WHERE e.at IS NULL OR e.at <= $T "
    "RETURN type(e) AS rel, e.at AS at LIMIT 50"
)


def to_hid(actor: str) -> str:
    return actor if HID.match(actor) else identifier_hash(actor)


def as_of_time(
    client: FalkorClient, org: str, T: int | None, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> tuple[int, bool]:
    """(T, defaulted). With no T given, the time of the newest event in the org graph."""
    if T is not None:
        return sc.checked_time(T), False
    r = ro_query(client, sc.graph_for(org), NEWEST_QUERY, {}, timeout_ms=timeout_ms)
    times = [t for t in (r.result_set[0] if r.result_set else []) if t is not None]
    if not times:
        raise ValueError(f"org graph {sc.graph_for(org)} has no events, so there is no default T")
    return int(max(times)), True


def _stamp(out: dict, org: str, t: int, defaulted: bool) -> dict:
    out.update(org=org, T=t, T_defaulted=defaulted)
    return out


def takeover_cost(client: FalkorClient, org: str, privilege: str, T: int | None = None) -> dict:
    t, d = as_of_time(client, org, T)
    r = cost.takeover_cost(client, org, privilege, t)
    return _stamp(
        {
            "privilege": privilege,
            "status": r.status,
            "cost": r.cost,
            "reason": r.reason,
            "path": r.path,
            "provisional": r.provisional,
            "rule": r.rule,
        },
        org,
        t,
        d,
    )


def guardians_(client: FalkorClient, org: str, privilege: str, T: int | None = None) -> dict:
    t, d = as_of_time(client, org, T)
    r = guardians.guardians(client, org, privilege, t)
    return _stamp(
        {
            "privilege": privilege,
            "status": r.status,
            "guardians": r.guardians,
            "reason": r.reason,
            "provisional": r.provisional,
            "rule": r.rule,
        },
        org,
        t,
        d,
    )


def org_normal(client: FalkorClient, org: str, T: int | None = None) -> dict:
    t, d = as_of_time(client, org, T)
    rows = run_as_of(
        client, sc.graph_for(org), NORMAL_QUERY, {"T": t}, timeout_ms=DEFAULT_TIMEOUT_MS
    ).result_set
    latest: dict[tuple, dict] = {}
    for metric, scope, window, at, value in rows:
        latest.setdefault(
            (metric, scope, window),
            {"metric": metric, "scope": scope, "window": window, "computed_at": at, "value": value},
        )
    return _stamp({"metrics": list(latest.values()), "found": bool(latest)}, org, t, d)


def trust_path_(
    client: FalkorClient, org: str, actor: str, privilege: str, T: int | None = None
) -> dict:
    t, d = as_of_time(client, org, T)
    hid = to_hid(actor)
    r = trust_path.trust_path(client, org, hid, privilege, t)
    return _stamp(
        {
            "actor_hid": hid,
            "privilege": privilege,
            "status": r.status,
            "weight": r.weight,
            "path": r.path,
            "hops": r.hops,
            "reason": r.reason,
            "edges_read": r.edges_read,
        },
        org,
        t,
        d,
    )


def claims_for(
    client: FalkorClient, org: str, actor: str, window: int = 90, T: int | None = None
) -> dict:
    """Claims the actor asserted in (T - window days, T]. `window` is in days."""
    t, d = as_of_time(client, org, T)
    hid = to_hid(actor)
    rows = run_as_of(
        client,
        sc.graph_for(org),
        CLAIMS_QUERY,
        {"hid": hid, "T": t, "since": t - int(window) * DAY_S},
        timeout_ms=DEFAULT_TIMEOUT_MS,
    ).result_set
    claims = [
        {
            "claim_id": cid,
            "kind": kind,
            "at": at,
            "target_hid": target,
            "quote": quote,
            "link": why_mod.source_link(stype, ref, link),
        }
        for cid, kind, at, target, quote, link, ref, stype in rows
    ]
    return _stamp({"actor_hid": hid, "window_days": int(window), "claims": claims}, org, t, d)


def check_trust(
    client: FalkorClient, org: str, actor: str, action: str, T: int | None = None
) -> dict:
    """Is this actor new, vouched for, and how near is `action` (a privilege kind)?

    This is evidence, not a verdict about a person (spec §4.4): history length, whether the frozen
    low-history rule applies, who vouched for them, whether they already hold the privilege, and
    the trust path to it. The Pressure and Vouch detectors' org-level status is included so the
    caller sees what the org's own detectors say at T. No score is produced.
    """
    t, d = as_of_time(client, org, T)
    hid = to_hid(actor)
    graph = sc.graph_for(org)
    th = lh.thresholds()["vouch"]

    rd = _reader(client, org, t)
    hist = lh.history(rd, [hid])
    if isinstance(hist, str):
        history = {"status": "NOT COMPUTED", "reason": hist}
    else:
        h = hist[hid]
        history = {
            "status": "COMPUTED",
            "days_in_org": round(h["days"], 2),
            "actions": h["actions"],
            "low_history": lh.is_low(h, th["low_history_days"], th["low_history_actions"]),
            "rule": f"low-history = < {th['low_history_days']} days or "
            f"< {th['low_history_actions']} actions (config/frozen.yaml)",
        }
    vouchers = [
        r[0]
        for r in run_as_of(
            client, graph, VOUCHED_BY_QUERY, {"hid": hid, "T": t}, timeout_ms=DEFAULT_TIMEOUT_MS
        ).result_set
    ]
    holds = [
        {"edge": rel, "at": at}
        for rel, at in run_as_of(
            client,
            graph,
            HOLDS_QUERY,
            {"hid": hid, "kind": action, "T": t},
            timeout_ms=DEFAULT_TIMEOUT_MS,
        ).result_set
    ]
    path = trust_path.trust_path(client, org, hid, action, t)
    det = {
        "pressure": pressure.pressure(client, org, t).status,
        "vouch": vouch.vouch(client, org, t).status,
    }
    return _stamp(
        {
            "actor_hid": hid,
            "action": action,
            "history": history,
            "vouched_for_by": vouchers,
            "already_holds": holds,
            "trust_path": {
                "status": path.status,
                "weight": path.weight,
                "hops": path.hops,
                "reason": path.reason,
            },
            "org_detectors": det,
            "note": "evidence for a human, not a verdict; no score is produced",
        },
        org,
        t,
        d,
    )


def _reader(client: FalkorClient, org: str, t: int):
    from core.detectors.common import Reader

    return Reader(client, org, t, DEFAULT_TIMEOUT_MS)


def visibility_gaps(decision: str, path: Path = GAPS_FILE) -> dict:
    """Computed gaps for one downstream decision, from the saved ecosystem run (roles only)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    known = [d["decision"] for d in doc["decisions"]]
    for d in doc["decisions"]:
        if d["decision"] == decision:
            return {
                "found": True,
                "decision": decision,
                "place": d["place"],
                "deciding_role": d["deciding_role"],
                "decision_at": d["decision_at"],
                "status": d["status"],
                "reason": d.get("reason"),
                "gaps": d.get("gaps", []),
                "query": d.get("query"),
                "source": f"eval/results/{path.name} (graph {doc['graph']})",
                "scope": doc["scope"],
            }
    return {"found": False, "decision": decision, "known_decisions": known}


def simulate_hardening(client: FalkorClient, org: str, step: str, T: int | None = None) -> dict:
    """One menu step on a copy of org_<org>: takeover cost and guardians before and after.

    The org graph is only read (GRAPH.COPY). Both scratch copies are dropped before returning.
    """
    if step not in sim.MENU:
        raise ValueError(f"unknown step {step!r}; menu is {list(sim.MENU)}")
    t, d = as_of_time(client, org, T)
    run = uuid.uuid4().hex[:10]
    harden, measured = f"harden_{run}", f"hsm{run}"
    try:
        before = sim.measure(client, org, t)
        client.copy(sc.graph_for(org), harden)
        changed = sim.apply_step(client, harden, step, t)
        client.copy(harden, sc.graph_for(measured))
        after = sim.measure(client, measured, t)
    finally:
        client.drop(harden)
        client.drop(sc.graph_for(measured))
    return _stamp(
        {
            "step": step,
            "menu": list(sim.MENU),
            "privilege": sim.PRIV,
            "before": before,
            "after": after,
            "graph_changes": changed,
            "changed_anything": any(bool(v) for v in changed.values()),
            "note": "measured on a copy; a step the cost does not read shows no change",
        },
        org,
        t,
        d,
    )


def why(client: FalkorClient, finding_id: str) -> dict:
    """The spec §7.6 why query for one finding id (`<case>:<quarter>`), live, with its Cypher."""
    case_id = finding_id.split(":", 1)[0]
    case = CASES.get(case_id)
    if case is None:
        return {"found": False, "finding_id": finding_id, "known_cases": sorted(CASES)}
    start = time.perf_counter()
    res = ro_query(
        client,
        case.graph,
        why_mod.WHY_CYPHER,
        {"id": finding_id},
        timeout_ms=why_mod.WHY_TIMEOUT_MS,
    )
    ms = (time.perf_counter() - start) * 1000
    rows = [
        {
            "kind": kind,
            "props": dict(props),
            "quote": quote,
            "link": why_mod.source_link(stype, ref, link),
            "source_ref": ref,
        }
        for _moves, kind, props, quote, link, ref, stype in res.result_set
    ]
    return {
        "found": bool(rows),
        "finding_id": finding_id,
        "label": case.label,
        "rows": rows,
        "query": {
            "cypher": why_mod.WHY_CYPHER,
            "ms": round(ms, 2),
            "timeout_ms": why_mod.WHY_TIMEOUT_MS,
        },
    }
