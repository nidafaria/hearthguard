"""Conflict links on a real FalkorDB graph (spec §6.1, §7.2). The policy is unchanged.

Hand-worked pairs (claims are created with the times shown):
  1. owner decision beats a hearsay claim  -> RESOLVED, CONTRADICTS link.
  2. equal authority, times 100 and 200  -> RESOLVED, SUPERSEDES newer->older.
  3. exception narrows a general claim   -> NARROWED, QUALIFIES exc->general.
  4. equal authority, same time          -> UNRESOLVED, no winner, CONTRADICTS.
Every pair keeps both claims. Writing a pair twice makes one link.
"""

import pytest

from core.claims import conflicts as cc
from core.policy import conflict as cf
from tests.fixtures.bd import q


@pytest.fixture
def claims(client, org_graph):
    q(
        client,
        org_graph,
        "CREATE (:Claim {id:'c-owner', at: 100}), (:Claim {id:'c-hearsay', at: 200}), "
        "(:Claim {id:'c-old', at: 100}), (:Claim {id:'c-new', at: 200}), "
        "(:Claim {id:'c-gen', at: 100}), (:Claim {id:'c-exc', at: 200}), "
        "(:Claim {id:'c-same1', at: 300}), (:Claim {id:'c-same2', at: 300})",
    )
    return f"org_{org_graph}"


def _links(client, org):
    return q(
        client, org, "MATCH (x:Claim)-[r]->(y:Claim) RETURN x.id, type(r), y.id ORDER BY x.id, y.id"
    ).result_set


def test_authority_resolves_and_links(client, org_graph, claims):
    res = cc.link_pair(
        client,
        claims,
        {"id": "c-owner", "source": "owner_decision"},
        {"id": "c-hearsay", "source": "hearsay"},
    )
    assert res.status == cf.RESOLVED and res.winner == "c-owner"
    assert ["c-owner", "CONTRADICTS", "c-hearsay"] in _links(client, org_graph)


def test_recency_writes_a_supersedes_from_newer_to_older(client, org_graph, claims):
    res = cc.link_pair(
        client,
        claims,
        {"id": "c-old", "source": "established_actor"},
        {"id": "c-new", "source": "established_actor"},
    )
    assert res.status == cf.RESOLVED and res.winner == "c-new"
    assert ["c-new", "SUPERSEDES", "c-old"] in _links(client, org_graph)


def test_specificity_writes_qualifies_from_exception_to_general(client, org_graph, claims):
    res = cc.link_pair(
        client,
        claims,
        {"id": "c-gen", "source": "established_actor"},
        {"id": "c-exc", "source": "established_actor", "exception_to": "c-gen"},
    )
    assert res.status == cf.NARROWED
    assert ["c-exc", "QUALIFIES", "c-gen"] in _links(client, org_graph)


def test_equal_authority_and_time_is_unresolved_and_picks_no_winner(client, org_graph, claims):
    res = cc.link_pair(
        client,
        claims,
        {"id": "c-same1", "source": "established_actor"},
        {"id": "c-same2", "source": "established_actor"},
    )
    assert res.status == cf.UNRESOLVED and res.winner is None
    assert any(r[1] == "CONTRADICTS" for r in _links(client, org_graph))


def test_writing_a_pair_twice_makes_one_link_and_keeps_both_claims(client, org_graph, claims):
    a = {"id": "c-owner", "source": "owner_decision"}
    b = {"id": "c-hearsay", "source": "hearsay"}
    cc.link_pair(client, claims, a, b)
    cc.link_pair(client, claims, a, b)
    assert _links(client, org_graph).count(["c-owner", "CONTRADICTS", "c-hearsay"]) == 1
    assert q(client, org_graph, "MATCH (c:Claim) RETURN count(c)").result_set[0][0] == 8


def test_a_claim_not_in_the_graph_is_refused(client, org_graph, claims):
    with pytest.raises(ValueError, match="not in graph"):
        cc.link_pair(
            client,
            claims,
            {"id": "c-owner", "source": "owner_decision"},
            {"id": "nope", "source": "hearsay"},
        )
