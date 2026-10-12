"""Hand-built org graphs with known takeover cost and guardians.

Every expected value below is derived by hand in the comment above it, from the rule in
docs/decisions/0001-outsider-edges.md (PROPOSED):
  - OUTSIDER reaches every actor with one entry hop. The hop is not counted in the cost.
  - cost = the fewest approvals along OUTSIDER -> actor -> privilege (CAN_GRANT approvals_required,
    GRANTED counts 1).
  - guardians = the fewest people that sit on every route (CAN_GRANT edges only, spec §7.4).
Nothing here is a finding about any real project. Hash ids are plain letters for readability.
"""

from collections.abc import Callable
from dataclasses import dataclass

from core.graph.client import FalkorClient

PRIV = "release"
T = 1_000  # the as-of time used by every case unless stated


@dataclass(frozen=True)
class Case:
    name: str
    build: Callable[[FalkorClient, str], None]  # (client, graph name)
    T: int
    cost: int | None
    cost_reason: str | None  # None when a cost is expected
    guardians: int
    path: tuple[str, ...] | None = None


def _privilege(client: FalkorClient, g: str) -> None:
    client.query(g, "CREATE (:Privilege {kind: $k, sensitive: true})", {"k": PRIV})


def _actor(client: FalkorClient, g: str, hid: str) -> None:
    client.query(g, "MERGE (:Actor {hid: $hid, kind: 'human'})", {"hid": hid})


def _edge(
    client: FalkorClient,
    g: str,
    hid: str,
    rel: str = "CAN_GRANT",
    approvals_required: int | None = None,
    at: int | None = None,
) -> None:
    """Edge from the actor to the privilege. Properties are only set when given."""
    sets, params = [], {"hid": hid, "k": PRIV}
    if approvals_required is not None:
        sets.append("e.approvals_required = $ar")
        params["ar"] = approvals_required
    if at is not None:
        sets.append("e.at = $at")
        params["at"] = at
    client.query(
        g,
        f"MATCH (a:Actor {{hid: $hid}}), (p:Privilege {{kind: $k}}) CREATE (a)-[e:{rel}]->(p)"
        + (" SET " + ", ".join(sets) if sets else ""),
        params,
    )


def case_a(client: FalkorClient, g: str) -> None:
    # a. Chain OUTSIDER -> A -> release. A alone can grant, and one approval is enough.
    #    Cost: the only route is through A and the CAN_GRANT edge needs 1 approval, so 1.
    #    Guardians: every route passes through A, so the smallest cut is {A}: 1.
    #    X is a bystander with no grant. It lies on no route and changes nothing.
    #    A's edge has no `at`, so it counts at any T (the rule for edges without a time).
    _privilege(client, g)
    for hid in ("A", "X"):
        _actor(client, g, hid)
    _edge(client, g, "A", approvals_required=1)


def case_b(client: FalkorClient, g: str) -> None:
    # b. A and B can both grant, each straight from OUTSIDER (two separate routes).
    #    A needs 1 approval, B needs 2.
    #    Cost: the cheaper route is through A: min(1, 2) = 1.
    #    Guardians: the routes share nothing but the ends, so one person cannot block both.
    #    The cut needs A and B: 2.
    _privilege(client, g)
    for hid in ("A", "B"):
        _actor(client, g, hid)
    _edge(client, g, "A", approvals_required=1, at=100)
    _edge(client, g, "B", approvals_required=2, at=200)


def case_c(client: FalkorClient, g: str) -> None:
    # c. Two-approval grant: A's CAN_GRANT needs approvals_required = 2.
    #    Cost: the outsider must win 2 approvals on the only route: 2.
    #    Guardians: still one person on every route, {A}: 1.
    _privilege(client, g)
    _actor(client, g, "A")
    _edge(client, g, "A", approvals_required=2, at=100)


def case_d(client: FalkorClient, g: str) -> None:
    # d. The privilege exists but nothing can grant it. A is an actor with no edge to it.
    #    Cost: there is no route, so no path (cost None, reason "no path"). Not an error.
    #    Guardians: with no route there is nothing to cut, so 0.
    _privilege(client, g)
    _actor(client, g, "A")


def case_e(client: FalkorClient, g: str) -> None:
    # e. A's grant is dated T + 1, one second after the as-of time T = 1000.
    #    At T the edge does not exist yet: no path, guardians 0.
    #    At T + 1 it exists: cost 1, guardians 1 (same as case a).
    _privilege(client, g)
    _actor(client, g, "A")
    _edge(client, g, "A", approvals_required=1, at=T + 1)


def case_f(client: FalkorClient, g: str) -> None:
    # f. (extra) A already holds the privilege: a GRANTED edge with no approval count.
    #    Cost: a holder is one human to win, so GRANTED counts 1 (PROPOSED default): 1.
    #    Guardians: the spec §7.4 projection reads CAN_GRANT only, so a GRANTED holder is not
    #    in the cut: 0. The two numbers disagree here. This is the open question in the
    #    decision file, pinned down so a change to either rule is noticed.
    _privilege(client, g)
    _actor(client, g, "A")
    _edge(client, g, "A", rel="GRANTED", at=100)


CASES: tuple[Case, ...] = (
    Case("a_single_chain", case_a, T, 1, None, 1, ("OUTSIDER", "A", f"PRIV:{PRIV}")),
    Case("b_two_keepers", case_b, T, 1, None, 2, ("OUTSIDER", "A", f"PRIV:{PRIV}")),
    Case("c_two_approvals", case_c, T, 2, None, 1, ("OUTSIDER", "A", f"PRIV:{PRIV}")),
    Case("d_no_path", case_d, T, None, "no path", 0),
    Case("e_grant_after_T", case_e, T, None, "no path", 0),
    Case("f_granted_holder", case_f, T, 1, None, 0, ("OUTSIDER", "A", f"PRIV:{PRIV}")),
)

# Case e again, but at T + 1, when the grant has happened.
CASE_E_AFTER = Case("e_grant_at_T_plus_1", case_e, T + 1, 1, None, 1)
