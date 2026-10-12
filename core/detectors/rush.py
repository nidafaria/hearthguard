"""Rush detector (docs/HEARTHGUARD.md §7.1): rights gained faster than the org normally grants.

Fires when an actor received a sensitive privilege with days-since-first-action BELOW this
organisation's own 10th percentile for that privilege. If the org has fewer than 5 historical
grants for that privilege at T, the fallback is 180 days. No LLM.

Method, written out so it can be checked by hand
------------------------------------------------
Subject: the actor's earliest GRANTED edge to the privilege with at <= T.
  days = (grant.at - first_action.at) / 86400, where first_action is the actor's earliest DID edge
  with at <= T.
History: every OTHER actor's earliest GRANTED edge to the privilege with at <= T (one entry per
  grantee, the tested actor left out so a grant is not judged against itself). n = their count.
Threshold:
  if n >= 5:  sort the history days ascending as x[0] <= x[1] <= ... <= x[n-1], then
              h = (n - 1) * 0.10
              threshold = x[floor(h)] + (h - floor(h)) * (x[ceil(h)] - x[floor(h)])
              (linear interpolation, the same as percentileCont(days, 0.10); rule 'org_p10')
  else:       threshold = 180 days (rule 'fallback_180d')
Fires when days < threshold (strictly below).
Example: ten grants of 100 days each: h = 0.9, threshold = 100 + 0.9 * (100 - 100) = 100.
         A grant after 20 days fires; after 150 days does not.

Missing data is never defaulted. A grant with no `at` (the subject's or anyone's), or a grantee
with an action with no `at` or with no action at all, makes the result NOT_COMPUTED.
"""

import hashlib
import math

from core.detectors.common import (
    FIRED,
    NOT_COMPUTED,
    NOT_FIRED,
    DetectorResult,
    Reader,
)
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import scratch as sc

DAY_S = 86_400
PERCENTILE = 0.10
MIN_HISTORY_GRANTS = 5
FALLBACK_DAYS = 180
HID_CHUNK = 500  # grantees looked up per query, so each result stays under the 1,000-row cap
MAX_HISTORY_LISTED = 200

GRANTS_QUERY = (
    "MATCH (a:Actor)-[e:GRANTED]->(p:Privilege {kind: $kind}) "
    "WHERE (e.at IS NULL OR e.at <= $T) "
    "RETURN a.hid AS hid, e.at AS at ORDER BY hid, at"
)

FIRST_ACTION_QUERY = (
    "MATCH (a:Actor)-[d:DID]->(x:Action) "
    "WHERE a.hid IN $hids AND (d.at IS NULL OR d.at <= $T) "
    "RETURN a.hid AS hid, min(d.at) AS first_at, count(d) AS n, count(d.at) AS n_dated LIMIT 1000"
)


def percentile_cont(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (see the module comment for the formula)."""
    xs = sorted(values)
    h = (len(xs) - 1) * q
    lo, hi = math.floor(h), math.ceil(h)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def grant_id_hash(hid: str, kind: str, at: int) -> str:
    """A stable id for one grant, from already-hashed parts. Carries no name or email."""
    return hashlib.sha256(f"GRANTED|{hid}|{kind}|{at}".encode()).hexdigest()


def decide(subject_days: float, history_days: list[float]) -> tuple[bool, float, str]:
    """Pure decision: (fired, threshold in days, rule used)."""
    if len(history_days) >= MIN_HISTORY_GRANTS:
        threshold, rule = percentile_cont(history_days, PERCENTILE), "org_p10"
    else:
        threshold, rule = float(FALLBACK_DAYS), "fallback_180d"
    return subject_days < threshold, threshold, rule


def rush(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    actor_hid: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> DetectorResult:
    T = sc.checked_time(T)
    res = DetectorResult("rush", org, T, NOT_COMPUTED)
    rd = Reader(client, org, T, timeout_ms)

    exists, rec = sc.privilege_exists(client, org, privilege_kind, timeout_ms)
    rd.add(rec)
    if not exists:
        where = (
            f"org graph {sc.graph_for(org)} does not exist"
            if rec.rows is None
            else f"no Privilege of kind '{privilege_kind}' in {sc.graph_for(org)}, so no grant data"
        )
        res.reason = where
        return rd.finish(res)

    rows = rd.paged("read_grants", GRANTS_QUERY, {"kind": privilege_kind})
    subject_rows = [r for r in rows if r[0] == actor_hid]
    if not subject_rows:
        res.status = NOT_FIRED
        res.reason = "no grant of this privilege to this actor at or before T"
        res.evidence = {"grants_read": len(rows)}
        return rd.finish(res)

    undated = [r for r in rows if r[1] is None]
    if undated:
        res.reason = "grant without timestamp"
        res.evidence = {"grants_without_timestamp": len(undated)}
        return rd.finish(res)

    earliest: dict[str, int] = {}  # one entry per grantee: the earliest grant
    for hid, at in rows:
        earliest[hid] = min(at, earliest.get(hid, at))

    first_action = _first_actions(rd, list(earliest))
    if isinstance(first_action, str):
        res.reason = first_action
        return rd.finish(res)

    days = {hid: (at - first_action[hid]) / DAY_S for hid, at in earliest.items()}
    history = [d for hid, d in days.items() if hid != actor_hid]
    fired, threshold, rule = decide(days[actor_hid], history)

    res.status = FIRED if fired else NOT_FIRED
    res.reason = (
        f"{days[actor_hid]:.2f} days from first action to grant is "
        f"{'below' if fired else 'not below'} the threshold of {threshold:.2f} days ({rule})"
    )
    res.evidence = {
        "grant_id_hash": grant_id_hash(actor_hid, privilege_kind, earliest[actor_hid]),
        "days": days[actor_hid],
        "threshold_days": threshold,
        "rule": rule,
        "n_history": len(history),
        "percentile": PERCENTILE if rule == "org_p10" else None,
        "min_history_grants": MIN_HISTORY_GRANTS,
        "fallback_days": FALLBACK_DAYS,
        "history_days": sorted(history) if len(history) <= MAX_HISTORY_LISTED else None,
    }
    return rd.finish(res)


def _first_actions(rd: Reader, hids: list[str]) -> dict[str, int] | str:
    """First action time per grantee, or a NOT_COMPUTED reason string."""
    found: dict[str, int] = {}
    for i in range(0, len(hids), HID_CHUNK):
        chunk = hids[i : i + HID_CHUNK]
        for hid, first_at, n, n_dated in rd.as_of(
            "first_action", FIRST_ACTION_QUERY, {"hids": chunk}
        ).result_set:
            if n != n_dated:
                return "action without timestamp"
            found[hid] = first_at
    missing = [h for h in hids if h not in found]
    if missing:
        return "grantee without a recorded action"
    return found
