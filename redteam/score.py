"""Scorer: run the frozen detectors and decide_with_unknowns on a planted copy (spec 8.5, 10.2).

Nothing here changes a detector, the conflict policy or the decision policy. It calls them.

How a campaign is judged, in one place (these definitions are written into every output file):
  evaluation points  the times of the campaign's own moves (claims, grant, release), in order.
                     At each point T the frozen detectors run as of T on the copy and
                     decide_with_unknowns() gives the decision.
  caught             the decision is NOTE or WATCH at any evaluation point (so by the last move).
  lead time          days from the first evaluation point whose decision is NOTE or WATCH to the
                     campaign's final action. The final action is the Bypass release when the
                     campaign has one, else its last move. Not defined for a missed campaign.
  moves at T         PRESSURE and VOUCH: the detector run as of T. RUSH: every grant to a
                     Privilege made after E0 and at or before T, each judged by the Rush detector;
                     FIRED if any fired, NOT_COMPUTED if none fired and any could not be computed,
                     else NOT_FIRED. BYPASS: the same over releases made after E0.
  lone keeper        the Lone keeper detector for the campaign's privilege as of T.

The scorer is the only code that reads planted/campaign_id/synthetic. It does not read them: the
campaign list comes from the generator, and detectors read the graph. A test strips the flags and
shows no detector result changes.

Forgetful memory (memory ablation): forget() removes from a copy every event older than T - W
days, every Normal node, every visibility edge and every remembered first-seen time, then the same
detectors run. See eval/ablation_memory.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from core.detectors import bypass, lone_keeper, pressure, rush, vouch
from core.detectors.common import FIRED, NOT_COMPUTED, NOT_FIRED
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from core.policy import decision as dec
from redteam import plant

CAUGHT_KINDS = ("NOTE", "WATCH")

Q_GRANTS_SINCE = (
    "MATCH (a:Actor)-[g:GRANTED]->(p:Privilege) "
    "WHERE g.at > $e0 AND g.at <= $T "
    "RETURN a.hid AS hid, p.kind AS priv, g.at AS at ORDER BY at, hid LIMIT 1000"
)
Q_RELEASES_SINCE = (
    "MATCH (x:Action {kind: 'release'}) WHERE x.at > $e0 AND x.at <= $T "
    "RETURN x.ref AS ref, x.at AS at ORDER BY at, ref LIMIT 1000"
)


def _agg(statuses: list[str]) -> str:
    if FIRED in statuses:
        return FIRED
    if NOT_COMPUTED in statuses:
        return NOT_COMPUTED
    return NOT_FIRED


@dataclass
class Point:
    """The state of the world judged at one evaluation time."""

    T: int
    moves: dict[str, str]
    lone_keeper: str
    decision: str
    detail: str | None = None
    reasons: dict[str, str | None] = field(default_factory=dict)


def judge(
    client: FalkorClient,
    org: str,
    privilege: str,
    T: int,
    e0: int,
    cache: dict | None = None,
) -> Point:
    """Run the frozen detectors on org_<org> as of T and apply decide_with_unknowns().

    `cache` (optional) memoises Rush and Bypass per grant or release for a graph whose past never
    changes between points (full memory). Do not share a cache across forgetful graphs.
    """
    cache = cache if cache is not None else {}
    reasons: dict[str, str | None] = {}
    p = pressure.pressure(client, org, T)
    v = vouch.vouch(client, org, T)
    reasons["PRESSURE"], reasons["VOUCH"] = p.reason, v.reason

    graph = f"org_{org}"
    grants = run_as_of(client, graph, Q_GRANTS_SINCE, {"e0": e0, "T": T}).result_set
    rush_statuses = []
    for hid, priv, at in grants:
        key = ("rush", hid, priv, at)
        if key not in cache:
            cache[key] = rush.rush(client, org, priv, hid, T)
        rush_statuses.append(cache[key].status)
    releases = run_as_of(client, graph, Q_RELEASES_SINCE, {"e0": e0, "T": T}).result_set
    bypass_statuses = []
    for ref, _at in releases:
        key = ("bypass", ref)
        if key not in cache:
            cache[key] = bypass.bypass(client, org, ref, T)
        bypass_statuses.append(cache[key].status)

    moves = {
        "PRESSURE": p.status,
        "VOUCH": v.status,
        "RUSH": _agg(rush_statuses),
        "BYPASS": _agg(bypass_statuses),
    }
    lk = lone_keeper.lone_keeper(client, org, privilege, T)
    lone = {lone_keeper.FLAG_SET: True, lone_keeper.FLAG_NOT_SET: False}.get(lk.status)
    e = dec.evidence_from_moves(moves, lone)
    result = dec.decide_with_unknowns(e)
    kind = type(result).__name__
    return Point(
        T=T,
        moves=moves,
        lone_keeper=lk.status,
        decision=kind,
        detail=getattr(result, "reason", None) or getattr(result, "pattern", None),
        reasons=reasons,
    )


def forget(client: FalkorClient, graph: str, T: int, window_days: int) -> None:
    """Make `graph` (a COPY) a forgetful memory as of T: keep only the last `window_days` days.

    Removed: Actions older than T - W (with their DID edges and Paths), Claims older than T - W,
    GRANTED edges older than T - W, every Normal node (no remembered normal), visibility edges and
    nodes (PARTICIPATES_IN, WATCHES, Place; no visibility memory), every remembered first-seen time
    on an Actor, and then actors with nothing left. Kept: Privilege nodes and CAN_GRANT edges (the
    current structure) and SHARES edges between actors who remain.
    """
    plant.assert_copy(graph)
    cut = T - window_days * plant.DAY_S
    steps = [
        ("MATCH (x:Action) WHERE x.at < $cut DETACH DELETE x", {"cut": cut}),
        ("MATCH (c:Claim) WHERE c.at < $cut DETACH DELETE c", {"cut": cut}),
        ("MATCH ()-[g:GRANTED]->() WHERE g.at < $cut DELETE g", {"cut": cut}),
        ("MATCH (n:Normal) DETACH DELETE n", {}),
        ("MATCH ()-[w:PARTICIPATES_IN|WATCHES]->() DELETE w", {}),
        ("MATCH (pl:Place) DETACH DELETE pl", {}),
        ("MATCH (p:Path) WHERE NOT ()-[:VIA]->(p) DETACH DELETE p", {}),
        ("MATCH (a:Actor) SET a.first_seen_in_org = null", {}),
        (
            "MATCH (a:Actor) WHERE NOT (a)-[:DID|ASSERTED|GRANTED|CAN_GRANT]->() DETACH DELETE a",
            {},
        ),
    ]
    for cypher, params in steps:
        client.query(graph, cypher, params, timeout_ms=plant.WRITE_TIMEOUT_MS)


def judge_forgetful(
    client: FalkorClient, source_org: str, privilege: str, T: int, e0: int, window_days: int
) -> Point:
    """Copy org_<source_org>, forget all but the last W days as of T, judge, drop the copy."""
    tmp = f"rtf{uuid.uuid4().hex[:10]}"
    graph = f"org_{tmp}"
    try:
        client.drop(graph)
        client.copy(f"org_{source_org}", graph)
        forget(client, graph, T, window_days)
        return judge(client, tmp, privilege, T, e0, cache=None)
    finally:
        client.drop(graph)


@dataclass
class Outcome:
    campaign_id: str
    index: int
    moves: list[str]
    patience_days: int
    privilege: str
    clean: bool
    caught: bool
    first_flag_day: float | None
    last_move_day: float
    final_day: float
    lead_time_days: float | None
    points: list[dict]

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def score_campaign(
    client: FalkorClient,
    org: str,
    camp,
    resolved: dict,
    e0: int,
    *,
    memory_window_days: int | None = None,
) -> Outcome:
    """Judge one planted campaign in org_<org> at each of its move times."""
    move_rows = sorted(
        {(r["at"], r["day"]) for r in resolved["events"] if r["move"]}
        if not camp.clean
        else {(r["at"], r["day"]) for r in resolved["events"] if r["kind"] in ("grant", "release")}
    )
    cache: dict = {}
    points = []
    first_flag_day = None
    for at, day in move_rows:
        if memory_window_days is None:
            pt = judge(client, org, camp.privilege, at, e0, cache)
        else:
            pt = judge_forgetful(client, org, camp.privilege, at, e0, memory_window_days)
        flagged = pt.decision in CAUGHT_KINDS
        if flagged and first_flag_day is None:
            first_flag_day = day
        points.append(
            {
                "day": day,
                "T": at,
                "moves": pt.moves,
                "lone_keeper": pt.lone_keeper,
                "decision": pt.decision,
                "detail": pt.detail,
            }
        )
    last_move_day = max(day for _at, day in move_rows) if move_rows else camp.final_day
    caught = first_flag_day is not None
    return Outcome(
        campaign_id=camp.id,
        index=camp.index,
        moves=list(camp.moves),
        patience_days=camp.patience_days,
        privilege=camp.privilege,
        clean=camp.clean,
        caught=caught,
        first_flag_day=first_flag_day,
        last_move_day=last_move_day,
        final_day=camp.final_day,
        lead_time_days=(camp.final_day - first_flag_day) if caught else None,
        points=points,
    )


def median(values: list[float]) -> float | None:
    xs = sorted(values)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def summarise(outcomes: list[Outcome]) -> dict:
    caught = [o for o in outcomes if o.caught]
    leads = [o.lead_time_days for o in caught if o.lead_time_days is not None]
    n = len(outcomes)
    decisions: dict[str, int] = {}
    for o in outcomes:
        last = o.points[-1]["decision"] if o.points else "NONE"
        decisions[last] = decisions.get(last, 0) + 1
    return {
        "n": n,
        "caught": len(caught),
        "missed": n - len(caught),
        "detection_rate": (len(caught) / n) if n else None,
        "median_lead_time_days": median(leads),
        "decision_at_last_move": dict(sorted(decisions.items())),
    }
