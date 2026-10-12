"""Hand-built org graphs with known detector results.

Every expected result is derived by hand in the comment above its case. Nothing here is a finding
about any real project. Ids are plain letters for readability. Times are day numbers * 86400 s.

Rush method (core/detectors/rush.py): days = grant - first action. History = every OTHER grantee's
days, at <= T. With 5 or more, threshold = 10th percentile (linear interpolation:
h = (n-1) * 0.10, x[floor h] + (h - floor h) * (x[ceil h] - x[floor h])). With fewer, 180 days.
Fires when days < threshold.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from core.graph.client import FalkorClient
from tests.fixtures import takeover_cases as tc

DAY = 86_400
PRIV = tc.PRIV
T_DAY = 3_000
T = T_DAY * DAY  # as-of time for the rush cases


# ------------------------------------------------------------------ shared builders
def _org(client: FalkorClient, g: str, pack: str) -> None:
    client.query(g, "CREATE (:Org {id: 'fixture', pack: $pack})", {"pack": pack})


def _privilege(client: FalkorClient, g: str) -> None:
    client.query(g, "CREATE (:Privilege {kind: $k, sensitive: true})", {"k": PRIV})


def _grantee(
    client: FalkorClient,
    g: str,
    hid: str,
    first_action_day: int | None,
    grant_at: int | None,
    dated: bool = True,
) -> None:
    """An actor, optionally with a first action, and a GRANTED edge (with or without `at`)."""
    client.query(g, "MERGE (:Actor {hid: $hid, kind: 'human'})", {"hid": hid})
    if first_action_day is not None:
        client.query(
            g,
            "MATCH (a:Actor {hid: $hid}) "
            "CREATE (a)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) "
            "SET d.at = $at",
            {"hid": hid, "ref": f"first_{hid}", "at": first_action_day * DAY},
        )
    if grant_at is not None:
        set_at = " SET e.at = $at" if dated else ""
        client.query(
            g,
            "MATCH (a:Actor {hid: $hid}), (p:Privilege {kind: $k}) "
            f"CREATE (a)-[e:GRANTED]->(p){set_at}",
            {"hid": hid, "k": PRIV, "at": grant_at},
        )


def _history(client: FalkorClient, g: str, n: int, undated_last: bool = False) -> None:
    """n grantees, each granted 100 days after their first action (days 1000 -> 1100)."""
    for i in range(1, n + 1):
        dated = not (undated_last and i == n)
        _grantee(client, g, f"H{i}", 1000, 1100 * DAY, dated)


# ------------------------------------------------------------------ Rush
@dataclass(frozen=True)
class RushCase:
    name: str
    build: Callable[[FalkorClient, str], None]
    actor: str
    T: int
    status: str
    reason_contains: str
    days: float | None = None
    threshold: float | None = None
    rule: str | None = None
    n_history: int | None = None


def rush_a(client, g):
    # a. 10 historical grants of exactly 100 days. New grant S after 20 days (day 2000 -> 2020).
    #    Threshold: n = 10 >= 5, h = 9 * 0.10 = 0.9, x[0] = x[1] = 100, so 100 + 0.9 * 0 = 100.
    #    20 < 100: FIRED.
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 10)
    _grantee(client, g, "S", 2000, 2020 * DAY)


def rush_b(client, g):
    # b. Same org. S is granted after 150 days (day 2000 -> 2150). Threshold 100.
    #    150 < 100 is false: NOT_FIRED.
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 10)
    _grantee(client, g, "S", 2000, 2150 * DAY)


def rush_c(client, g):
    # c. Only 3 historical grants: fewer than 5, so the 180-day fallback applies.
    #    S is granted after 90 days. 90 < 180: FIRED, rule fallback_180d.
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 3)
    _grantee(client, g, "S", 2000, 2090 * DAY)


def rush_d(client, g):
    # d. 5 historical grants, one of them with no `at`. Its date cannot be known, so it cannot be
    #    placed in the distribution or before T. NOT_COMPUTED, reason "grant without timestamp".
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 5, undated_last=True)
    _grantee(client, g, "S", 2000, 2020 * DAY)


def rush_e(client, g):
    # e. 5 historical grants of 100 days. S is granted after 90 days (day 2000 -> 2090).
    #    Z is granted ONE SECOND AFTER T, with days = 1 + 1/86400 (first action day 2999).
    #    At T: Z does not exist yet. History = 5 x 100, threshold 100, 90 < 100: FIRED, n = 5.
    #    If Z leaked into T the history would be [1.0000116, 100 x 5], h = 5 * 0.10 = 0.5,
    #    threshold 1.0000116 + 0.5 * (100 - 1.0000116) = 50.5000058, and 90 would NOT fire.
    #    At T + 1: Z is history, n = 6, threshold 50.5000058, 90 is not below it: NOT_FIRED.
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 5)
    _grantee(client, g, "S", 2000, 2090 * DAY)
    _grantee(client, g, "Z", 2999, T + 1)


def rush_f(client, g):
    # f. S has a grant but no recorded action at all, so days-since-first-action is undefined.
    #    NOT_COMPUTED, reason "grantee without a recorded action".
    _org(client, g, "oss")
    _privilege(client, g)
    _history(client, g, 5)
    _grantee(client, g, "S", None, 2020 * DAY)


RUSH_CASES: tuple[RushCase, ...] = (
    RushCase("a_fast_grant", rush_a, "S", T, "FIRED", "below", 20.0, 100.0, "org_p10", 10),
    RushCase("b_slow_grant", rush_b, "S", T, "NOT_FIRED", "not below", 150.0, 100.0, "org_p10", 10),
    RushCase("c_fallback_180", rush_c, "S", T, "FIRED", "below", 90.0, 180.0, "fallback_180d", 3),
    RushCase("d_grant_without_at", rush_d, "S", T, "NOT_COMPUTED", "grant without timestamp"),
    RushCase(
        "e_future_grant_excluded", rush_e, "S", T, "FIRED", "below", 90.0, 100.0, "org_p10", 5
    ),
    # e2: Z asked about at T. Z's only grant is at T + 1, so there is no grant to judge at T.
    RushCase("e2_subject_grant_after_T", rush_e, "Z", T, "NOT_FIRED", "no grant"),
    RushCase("f_no_action", rush_f, "S", T, "NOT_COMPUTED", "grantee without a recorded action"),
)
# e again, one second later, when Z's grant is part of the history.
RUSH_E_LATER = RushCase(
    "e_later_T_includes_Z", rush_e, "S", T + 1, "NOT_FIRED", "not below", 90.0, 50.5, "org_p10", 6
)


# ------------------------------------------------------------------ Bypass
OSS_FULL = {
    "channel": "ci",
    "verified": True,
    "ci": True,
    "provenance": True,
    "key_hid": "k1",
    "publisher_in_set": True,
    "artifact_matches_tag": True,
}
FIN_USUAL = {"channel": "portal", "callback": True, "approvers": 2}
ACTION_DAY = 200


def _path_action(client, g, ref: str, day: int, props: dict, kind: str = "release") -> None:
    """An action with its own Path node. Only the given properties are set."""
    inline = ", ".join(f"{k}: $v_{k}" for k in props)
    params = {f"v_{k}": v for k, v in props.items()}
    client.query(
        g,
        f"CREATE (:Action {{ref: $ref, kind: $kind, at: $at}})-[:VIA]->(:Path {{{inline}}})",
        {"ref": ref, "kind": kind, "at": day * DAY, **params},
    )


def _bypass_org(client, g, pack: str, history: list[dict], action: dict, action_day=ACTION_DAY):
    _org(client, g, pack)
    for i, props in enumerate(history, start=1):
        _path_action(client, g, f"hist_{i}", 100 + i, props)
    _path_action(client, g, "new", action_day, action)


@dataclass(frozen=True)
class BypassCase:
    name: str
    build: Callable[[FalkorClient, str], None]
    T: int
    status: str
    differing: tuple[str, ...] = ()
    not_computed: tuple[str, ...] = ()
    reason_contains: str | None = None
    prop_status: dict = field(default_factory=dict)


BT = 400 * DAY  # as-of time for the bypass cases (after the action at day 200)


def bypass_f(client, g):
    # f. Three earlier releases all went out through CI. The new one went by email.
    #    Only `channel` differs (ci vs email); the other six properties are equal.
    #    FIRED, differing = ["channel"].
    _bypass_org(client, g, "oss", [OSS_FULL] * 3, {**OSS_FULL, "channel": "email"})


def bypass_g(client, g):
    # g. The earlier paths never recorded `ci`; the new path has ci = True. There is nothing to
    #    compare it with, so `ci` is NOT_COMPUTED, not a match and not a difference.
    #    The other six match. Overall NOT_COMPUTED (not FIRED, not NOT_FIRED).
    no_ci = {k: v for k, v in OSS_FULL.items() if k != "ci"}
    _bypass_org(client, g, "oss", [no_ci] * 3, OSS_FULL)


def bypass_g2(client, g):
    # g2. The reverse: earlier paths have ci, the new path does not record it. NOT_COMPUTED for ci.
    no_ci = {k: v for k, v in OSS_FULL.items() if k != "ci"}
    _bypass_org(client, g, "oss", [OSS_FULL] * 3, no_ci)


def bypass_h(client, g):
    # h. All seven properties equal the normal. NOT_FIRED.
    _bypass_org(client, g, "oss", [OSS_FULL] * 3, dict(OSS_FULL))


def bypass_tie(client, g):
    # tie. Earlier channels: one 'ci', one 'email'. The normal channel is a tie, so it cannot be
    #     named. `channel` is NOT_COMPUTED. The other six match. Overall NOT_COMPUTED.
    _bypass_org(client, g, "oss", [OSS_FULL, {**OSS_FULL, "channel": "email"}], dict(OSS_FULL))


def bypass_no_history(client, g):
    # No earlier release at all, so there is no remembered normal: NOT_COMPUTED.
    _bypass_org(client, g, "oss", [], dict(OSS_FULL))


def bypass_after_T(client, g):
    # The action is dated day 200 but we ask at day 100 (before it). The action does not exist
    # yet at that time: NOT_COMPUTED.
    _bypass_org(client, g, "oss", [OSS_FULL] * 3, {**OSS_FULL, "channel": "email"})


def bypass_fin_fewer(client, g):
    # Finance. Earlier bank changes had 2 approvers. This one had 1: FEWER, so it differs.
    #    FIRED, differing = ["approvers"]. channel and callback match.
    _bypass_org(client, g, "finance", [FIN_USUAL] * 3, {**FIN_USUAL, "approvers": 1})


def bypass_fin_more(client, g):
    # Finance. Same normal (2 approvers). This one had 3: more approvers is not a bypass.
    #    All three properties match or are not lower: NOT_FIRED.
    _bypass_org(client, g, "finance", [FIN_USUAL] * 3, {**FIN_USUAL, "approvers": 3})


def bypass_fin_callback(client, g):
    # Finance. Earlier changes were confirmed by callback (True). This one was not (False).
    #    FIRED, differing = ["callback"].
    _bypass_org(client, g, "finance", [FIN_USUAL] * 3, {**FIN_USUAL, "callback": False})


BYPASS_CASES: tuple[BypassCase, ...] = (
    BypassCase("f_channel_changed", bypass_f, BT, "FIRED", differing=("channel",)),
    BypassCase(
        "g_normal_lacks_ci",
        bypass_g,
        BT,
        "NOT_COMPUTED",
        not_computed=("ci",),
        prop_status={"ci": "NOT_COMPUTED", "channel": "MATCHES"},
    ),
    BypassCase(
        "g2_action_lacks_ci",
        bypass_g2,
        BT,
        "NOT_COMPUTED",
        not_computed=("ci",),
        prop_status={"ci": "NOT_COMPUTED"},
    ),
    BypassCase("h_all_equal", bypass_h, BT, "NOT_FIRED"),
    BypassCase(
        "tie_channel",
        bypass_tie,
        BT,
        "NOT_COMPUTED",
        not_computed=("channel",),
        prop_status={"channel": "NOT_COMPUTED"},
    ),
    BypassCase("no_history", bypass_no_history, BT, "NOT_COMPUTED", reason_contains="no earlier"),
    BypassCase(
        "action_after_T", bypass_after_T, 100 * DAY, "NOT_COMPUTED", reason_contains="no action"
    ),
    BypassCase("fin_fewer_approvers", bypass_fin_fewer, BT, "FIRED", differing=("approvers",)),
    BypassCase("fin_more_approvers", bypass_fin_more, BT, "NOT_FIRED"),
    BypassCase("fin_no_callback", bypass_fin_callback, BT, "FIRED", differing=("callback",)),
)


# ------------------------------------------------------------------ Lone keeper
@dataclass(frozen=True)
class LoneCase:
    name: str
    build: Callable[[FalkorClient, str], None]
    T: int
    status: str
    flag: bool | None
    guardians: int | None = None
    active_keepers: int | None = None


def _commit_by(client, g, hid: str, at: int) -> None:
    client.query(g, "MERGE (:Actor {hid: $hid, kind: 'human'})", {"hid": hid})
    client.query(
        g,
        "MATCH (a:Actor {hid: $hid}) "
        "CREATE (a)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) SET d.at = $at",
        {"hid": hid, "ref": f"c_{hid}", "at": at},
    )


def lone_i1(client, g):
    # i1. Takeover case a: one keeper, guardians 1. Nobody has a commit, so active_keepers 0.
    #     guardians == 1: flag SET.
    tc.case_a(client, g)


def lone_i2(client, g):
    # i2. Takeover case b: two keepers, guardians 2. No commits, active_keepers 0.
    #     Neither is 1: flag NOT set.
    tc.case_b(client, g)


def lone_j(client, g):
    # j. An actor but no Privilege at all, so guardians is NOT COMPUTED. No silent fallback:
    #    Lone keeper is NOT_COMPUTED.
    client.query(g, "CREATE (:Actor {hid: 'A', kind: 'human'})")


def lone_k(client, g):
    # k. Two keepers (guardians 2) but exactly one author committed in the last 90 days
    #    (a commit at second 500, T = 1000). active_keepers == 1: flag SET.
    tc.case_b(client, g)
    _commit_by(client, g, "C", 500)


def lone_l(client, g):
    # l. Guardians 2 and two authors committed: active_keepers 2. Flag NOT set.
    tc.case_b(client, g)
    _commit_by(client, g, "C", 500)
    _commit_by(client, g, "D", 600)


LONE_CASES: tuple[LoneCase, ...] = (
    LoneCase("i1_guardians_1", lone_i1, tc.T, "FLAG_SET", True, 1, 0),
    LoneCase("i2_guardians_2", lone_i2, tc.T, "FLAG_NOT_SET", False, 2, 0),
    LoneCase("j_guardians_not_computed", lone_j, tc.T, "NOT_COMPUTED", None),
    LoneCase("k_one_active_keeper", lone_k, tc.T, "FLAG_SET", True, 2, 1),
    LoneCase("l_two_active_keepers", lone_l, tc.T, "FLAG_NOT_SET", False, 2, 2),
)


# ------------------------------------------------------------------ Bypass: shared Path nodes
# Some ingests give many actions the SAME Path node (the xz git ingest does). Comparing an action
# with a normal built from its own node is a self-comparison, not evidence. Rules
# (core/detectors/bypass.py):
#   - the action and every earlier action use ONE Path node -> whole check NOT_COMPUTED,
#     reason "single shared Path node, no variation to compare";
#   - the action's own node is shared (used by more than one action at <= T): a property is
#     comparable only if the earlier actions show at least two distinct values for it;
#   - an action whose own node is used by that action alone has no such limit.
SHARED_REASON = "single shared Path node, no variation to compare"
MANUAL = {**OSS_FULL, "channel": "manual"}


def _shared_node(client, g, tag: str, props: dict) -> None:
    inline = ", ".join(["node: $tag", *[f"{k}: $v_{k}" for k in props]])
    params = {"tag": tag, **{f"v_{k}": v for k, v in props.items()}}
    client.query(g, f"CREATE (:Path {{{inline}}})", params)


def _use(client, g, tag: str, ref: str, day: int) -> None:
    client.query(
        g,
        "MATCH (p:Path {node: $tag}) "
        "CREATE (:Action {ref: $ref, kind: 'release', at: $at})-[:VIA]->(p)",
        {"tag": tag, "ref": ref, "at": day * DAY},
    )


def bypass_shared_single(client, g):
    # One Path node, used by three earlier releases and by the new one. The action's path is the
    # normal's only source: nothing varies. The whole check is NOT_COMPUTED with the shared reason.
    _org(client, g, "oss")
    _shared_node(client, g, "n1", OSS_FULL)
    for i in (1, 2, 3):
        _use(client, g, "n1", f"hist_{i}", 100 + i)
    _use(client, g, "n1", "new", ACTION_DAY)


def _two_shared_nodes(client, g, new_on: str):
    _org(client, g, "oss")
    _shared_node(client, g, "n1", OSS_FULL)  # channel ci
    _shared_node(client, g, "n2", MANUAL)  # channel manual, everything else the same
    for i in (1, 2, 3):
        _use(client, g, "n1", f"hist_{i}", 100 + i)
    for i in (4, 5):
        _use(client, g, "n2", f"hist_{i}", 100 + i)
    _use(client, g, new_on, "new", ACTION_DAY)


def bypass_two_nodes_match(client, g):
    # Earlier channels: ci x3 (node n1), manual x2 (node n2). Two distinct values, so channel is
    # comparable. The normal is ci (3 votes to 2). The new release is on n1 (ci): MATCHES.
    # The other six properties have ONE value across all earlier paths and the action's node is
    # shared, so each is NOT_COMPUTED. Overall NOT_COMPUTED.
    _two_shared_nodes(client, g, "n1")


def bypass_two_nodes_differs(client, g):
    # Same history. The new release is on n2 (manual), which the normal (ci) does not match:
    # channel DIFFERS. The other six are NOT_COMPUTED as above. FIRED, differing = ["channel"].
    _two_shared_nodes(client, g, "n2")


def bypass_own_path_unshared(client, g):
    # Three earlier releases share node n1 (channel ci). The new release has its OWN node
    # (channel email), used by that one action: two distinct nodes, and the action's node is not
    # shared, so every property is comparable. channel DIFFERS (ci vs email); the other six equal.
    # FIRED, differing = ["channel"], nothing NOT_COMPUTED.
    _org(client, g, "oss")
    _shared_node(client, g, "n1", OSS_FULL)
    for i in (1, 2, 3):
        _use(client, g, "n1", f"hist_{i}", 100 + i)
    _path_action(client, g, "new", ACTION_DAY, {**OSS_FULL, "channel": "email"})


SIX_FLAT = ("verified", "ci", "provenance", "key_hid", "publisher_in_set", "artifact_matches_tag")

BYPASS_SHARED_CASES: tuple[BypassCase, ...] = (
    BypassCase(
        "shared_single_node",
        bypass_shared_single,
        BT,
        "NOT_COMPUTED",
        reason_contains=SHARED_REASON,
    ),
    BypassCase(
        "two_shared_nodes_channel_matches",
        bypass_two_nodes_match,
        BT,
        "NOT_COMPUTED",
        not_computed=SIX_FLAT,
        prop_status={"channel": "MATCHES", "verified": "NOT_COMPUTED"},
    ),
    BypassCase(
        "two_shared_nodes_channel_differs",
        bypass_two_nodes_differs,
        BT,
        "FIRED",
        differing=("channel",),
        not_computed=SIX_FLAT,
    ),
    BypassCase(
        "own_unshared_path_is_comparable",
        bypass_own_path_unshared,
        BT,
        "FIRED",
        differing=("channel",),
        not_computed=(),
        prop_status={"verified": "MATCHES", "ci": "MATCHES"},
    ),
)
