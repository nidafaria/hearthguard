"""Bypass detector (docs/HEARTHGUARD.md §7.1): a sensitive action took an unusual path.

Compares the Path of one action against the remembered normal for its action kind, on the
properties its pack defines. Bypass is a single move: it can fire alone. No LLM.

Remembered normal, as of T
--------------------------
For each property, the most common value among the Paths of EARLIER actions of the same kind
(other actions, at <= the action's time, in the trailing 730 days, and at <= T). This is the same
window as the stored usual_path metric. A property is judged separately:
  - DIFFERS         the action's value differs from the normal. For `approvers` (finance) only
                    FEWER than the normal counts, as the spec says "fewer approvers than usual".
  - MATCHES         the action's value equals the normal.
  - NOT_COMPUTED    the property is absent on the action's side, absent from every earlier path, or
                    the earlier values tie for most common. Never counted as a match.
Overall: FIRED if any property DIFFERS (the differing names are listed); else NOT_FIRED only if
every property MATCHES; else NOT_COMPUTED, listing the properties that could not be compared.
"""

from collections import Counter

from core.detectors.common import (
    FIRED,
    NOT_COMPUTED,
    NOT_FIRED,
    DetectorResult,
    Reader,
)
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.normal.metrics import CHANNEL_WINDOW_DAYS
from core.takeover import scratch as sc

DAY_S = 86_400

PACK_PROPERTIES: dict[str, tuple[str, ...]] = {
    "oss": (
        "channel",
        "verified",
        "ci",
        "provenance",
        "key_hid",
        "publisher_in_set",
        "artifact_matches_tag",
    ),
    "finance": ("channel", "callback", "approvers"),
}
# Properties where only a LOWER value than normal is a bypass.
FEWER_IS_BYPASS = frozenset({"approvers"})

DIFFERS = "DIFFERS"
MATCHES = "MATCHES"


def action_query(props: tuple[str, ...]) -> str:
    cols = ", ".join(f"p.{p} AS {p}" for p in props)
    return (
        "MATCH (a:Action {ref: $ref})-[:VIA]->(p:Path) "
        "WHERE a.at <= $T "
        f"RETURN a.kind AS kind, a.at AS at, {cols} LIMIT 10"
    )


def history_query(props: tuple[str, ...]) -> str:
    cols = ", ".join(f"p.{p} AS {p}" for p in props)
    return (
        "MATCH (a:Action {kind: $kind})-[:VIA]->(p:Path) "
        "WHERE a.at <= $T AND a.at <= $at AND a.at > $at - $window AND a.ref <> $ref "
        f"RETURN {cols} ORDER BY a.at, a.ref"
    )


def judge(prop: str, action_value, history_values: list) -> dict:
    """Pure: one property's verdict from the action's value and the earlier values."""
    present = [v for v in history_values if v is not None]
    if action_value is None:
        return {"status": NOT_COMPUTED, "reason": "property absent on the action's path"}
    if not present:
        return {"status": NOT_COMPUTED, "reason": "property absent from every earlier path"}
    counts = Counter(present).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return {"status": NOT_COMPUTED, "reason": "earlier values tie for most common"}
    normal, support = counts[0]
    if prop in FEWER_IS_BYPASS:
        differs = action_value < normal
    else:
        differs = action_value != normal
    verdict = {
        "status": DIFFERS if differs else MATCHES,
        "normal": normal,
        "action": action_value,
        "support": support,
        "of": len(present),
    }
    if prop in FEWER_IS_BYPASS and action_value > normal:
        verdict["note"] = "more than the normal is not a bypass"
    return verdict


def bypass(
    client: FalkorClient,
    org: str,
    action_ref: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> DetectorResult:
    T = sc.checked_time(T)
    res = DetectorResult("bypass", org, T, NOT_COMPUTED)
    rd = Reader(client, org, T, timeout_ms)

    pack = rd.plain("org_pack", "MATCH (o:Org) RETURN o.pack AS pack LIMIT 2").result_set
    packs = {row[0] for row in pack}
    if len(packs) != 1 or next(iter(packs)) not in PACK_PROPERTIES:
        res.reason = f"org pack is not one known pack: {sorted(map(str, packs))}"
        return rd.finish(res)
    pack_name = next(iter(packs))
    props = PACK_PROPERTIES[pack_name]

    acted = rd.as_of("action_path", action_query(props), {"ref": action_ref}).result_set
    if not acted:
        res.reason = "no action with this ref and a Path at or before T"
        return rd.finish(res)
    if len(acted) > 1:
        res.reason = "action has more than one Path"
        return rd.finish(res)
    kind, at, *action_values = acted[0]
    if kind is None or at is None:
        res.reason = "action has no kind or no timestamp"
        return rd.finish(res)

    hist = rd.paged(
        "history_paths",
        history_query(props),
        {"kind": kind, "at": at, "window": CHANNEL_WINDOW_DAYS * DAY_S, "ref": action_ref},
    )
    if not hist:
        res.reason = f"no earlier '{kind}' actions with a Path in the window, so no normal"
        res.evidence = {"action_kind": kind, "pack": pack_name, "history_actions": 0}
        return rd.finish(res)

    verdicts = {
        prop: judge(prop, action_values[i], [row[i] for row in hist])
        for i, prop in enumerate(props)
    }
    differing = [p for p, v in verdicts.items() if v["status"] == DIFFERS]
    not_computed = [p for p, v in verdicts.items() if v["status"] == NOT_COMPUTED]
    res.evidence = {
        "action_kind": kind,
        "pack": pack_name,
        "history_actions": len(hist),
        "window_days": CHANNEL_WINDOW_DAYS,
        "properties": verdicts,
        "differing": differing,
        "not_computed_properties": not_computed,
    }
    if differing:
        res.status = FIRED
        res.reason = "differs from the remembered normal on: " + ", ".join(differing)
    elif not_computed:
        res.reason = "properties that could not be compared: " + ", ".join(not_computed)
    else:
        res.status = NOT_FIRED
        res.reason = f"all {len(props)} properties match the remembered normal"
    return rd.finish(res)
