"""Who counts as a low-history actor (docs/HEARTHGUARD.md §7.1, Pressure and Vouch).

An actor is low-history at T if their history in this org is < 90 days OR they have < 5 actions
(both numbers from config/frozen.yaml). Read from the graph, only at <= T:
  history days = (T - earliest of Actor.first_seen_in_org and the actor's first DID edge) / 86400
  actions      = count of the actor's DID edges with at <= T
An actor with no first-seen time and no action cannot be judged, which makes the result
NOT_COMPUTED for the caller (never a guess).
"""

from pathlib import Path

import yaml

from core.detectors.common import Reader

DAY_S = 86_400
HID_CHUNK = 500
FROZEN_PATH = Path(__file__).resolve().parents[2] / "config" / "frozen.yaml"

HISTORY_QUERY = (
    "MATCH (a:Actor) WHERE a.hid IN $hids AND (a.first_seen_in_org IS NULL OR "
    "a.first_seen_in_org <= $T) "
    "OPTIONAL MATCH (a)-[d:DID]->(:Action) WHERE d.at <= $T "
    "WITH a, count(d) AS actions, min(d.at) AS first_did "
    "RETURN a.hid AS hid, a.first_seen_in_org AS seen, actions, first_did ORDER BY hid LIMIT 1000"
)


def thresholds() -> dict:
    return yaml.safe_load(FROZEN_PATH.read_text(encoding="utf-8"))


def history(rd: Reader, hids: list[str]) -> dict[str, dict] | str:
    """{hid: {days, actions}} or a NOT_COMPUTED reason string."""
    found: dict[str, dict] = {}
    for i in range(0, len(hids), HID_CHUNK):
        chunk = hids[i : i + HID_CHUNK]
        for hid, seen, actions, first_did in rd.as_of(
            "actor_history", HISTORY_QUERY, {"hids": chunk}
        ).result_set:
            times = [t for t in (seen, first_did) if t is not None]
            if not times:
                return "actor without a first-seen time or an action"
            found[hid] = {"days": (rd.T - min(times)) / DAY_S, "actions": actions}
    missing = [h for h in hids if h not in found]
    if missing:
        return "actor not found in the graph at T"
    return found


def is_low(h: dict, days_max: int, actions_min: int) -> bool:
    return h["days"] < days_max or h["actions"] < actions_min
