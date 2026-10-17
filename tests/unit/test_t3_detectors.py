"""Unit and integration tests for Team 3 detector improvements:
1. Pressure Condition 2 (keeper activity drop or capacity statement, default chosen for submission).
2. Vouch (Claim.target_hid population and SHARES edges builder, firing on real graph data).
3. Lone keeper (centrality fallback on approval/review graph when maxFlow fails / is NOT_COMPUTED).
"""

import pytest

from core.claims import graph_write, shares
from core.detectors import lone_keeper, pressure, vouch
from core.detectors.common import FIRED, NOT_COMPUTED, NOT_FIRED
from core.graph.client import FalkorClient
from core.takeover import scratch as sc

DAY = 86_400
T_DAY = 1000
T = T_DAY * DAY


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def org(client, request):
    org = "t3_" + request.node.name.split("[")[0].removeprefix("test_")[:30]
    client.drop(sc.graph_for(org))
    yield org
    client.drop(sc.graph_for(org))


def setup_low_actors(client, org):
    """Create two low-history actors A and B in sc.graph_for(org)."""
    g = sc.graph_for(org)
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human'}) SET a.first_seen_in_org = $sA "
        "MERGE (b:Actor {hid: 'B', kind: 'human'}) SET b.first_seen_in_org = $sB",
        {"sA": 990 * DAY, "sB": 995 * DAY},
    )


def add_pressure_claims(client, org):
    """Add 3 pressure claims from 2 low-history actors in window (880..1000]."""
    g = sc.graph_for(org)
    client.query(
        g,
        "MATCH (a:Actor {hid: 'A'}) CREATE (a)-[:ASSERTED]->"
        "(:Claim {id: 'c1', kind: 'PRESSURE', at: 950 * 86400})",
    )
    client.query(
        g,
        "MATCH (b:Actor {hid: 'B'}) CREATE (b)-[:ASSERTED]->"
        "(:Claim {id: 'c2', kind: 'URGENCY', at: 960 * 86400}), "
        "(b)-[:ASSERTED]->(:Claim {id: 'c3', kind: 'PRESSURE', at: 970 * 86400})",
    )


# ==============================================================================
# 1. Pressure Condition 2 Tests
# ==============================================================================


def test_pressure_condition2_keeper_capacity_statement_fires(client, org):
    """Condition (1) met and keeper makes a CAPACITY_STATEMENT in the window -> FIRED."""
    setup_low_actors(client, org)
    add_pressure_claims(client, org)
    g = sc.graph_for(org)

    # Keeper K with is_keeper = true
    client.query(g, "MERGE (k:Actor {hid: 'K', kind: 'human', is_keeper: true})")
    # Keeper K asserts a CAPACITY_STATEMENT at day 960
    client.query(
        g,
        "MATCH (k:Actor {hid: 'K'}) CREATE (k)-[:ASSERTED]->"
        "(:Claim {id: 'ck1', kind: 'CAPACITY_STATEMENT', at: 960 * 86400})",
    )

    res = pressure.pressure(client, org, T)
    assert res.status == FIRED
    assert "CAPACITY_STATEMENT" in res.reason
    assert "default chosen for submission, not final" in res.reason
    assert res.evidence["keeper_condition_met"] is True
    assert res.evidence["keeper_capacity_statement"] is True
    assert res.evidence["keeper_capacity_claim_ids"] == ["ck1"]


def test_pressure_condition2_keeper_activity_drop_fires(client, org):
    """Condition (1) met and keeper activity drops <= 50% of trailing median -> FIRED."""
    setup_low_actors(client, org)
    add_pressure_claims(client, org)
    g = sc.graph_for(org)

    # Keeper K holding CAN_GRANT
    client.query(
        g,
        "MERGE (k:Actor {hid: 'K', kind: 'human'}) "
        "MERGE (p:Privilege {kind: 'release'}) "
        "MERGE (k)-[:CAN_GRANT]->(p)",
    )

    # Add 10 commit actions per 90-day window in trailing 730 days (baseline: windows 1..7)
    # window 0 is [T - 90d, T] = [910d, 1000d]
    for w in range(1, 8):
        center_day = 1000 - w * 90 - 45
        for i in range(10):
            client.query(
                g,
                "MATCH (k:Actor {hid: 'K'}) "
                "CREATE (k)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) SET d.at = $at",
                {"ref": f"ref-w{w}-{i}", "at": (center_day * DAY) + i},
            )

    # In recent 90 days [910d..1000d], keeper performs only 1 action (1 / 10 = 0.1 <= 0.5)
    client.query(
        g,
        "MATCH (k:Actor {hid: 'K'}) "
        "CREATE (k)-[d:DID]->(:Action {kind: 'commit', ref: 'recent-1'}) SET d.at = 950 * 86400",
    )

    res = pressure.pressure(client, org, T)
    assert res.status == FIRED
    assert "keepers' activity in last 90 days" in res.reason
    assert "default chosen for submission, not final" in res.reason
    assert res.evidence["keeper_condition_met"] is True
    assert res.evidence["keeper_activity_recent"] == 1
    assert res.evidence["keeper_activity_median"] == 10.0
    assert res.evidence["keeper_activity_ratio"] <= 0.5


def test_pressure_condition2_keeper_activity_normal_not_fired(client, org):
    """Condition (1) met, but keeper activity is healthy (> 50% of median) -> NOT_FIRED."""
    setup_low_actors(client, org)
    add_pressure_claims(client, org)
    g = sc.graph_for(org)

    # Keeper K
    client.query(g, "MERGE (k:Actor {hid: 'K', kind: 'human', is_keeper: true})")

    # Baseline 10 actions per window
    for w in range(1, 8):
        center_day = 1000 - w * 90 - 45
        for i in range(10):
            client.query(
                g,
                "MATCH (k:Actor {hid: 'K'}) "
                "CREATE (k)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) SET d.at = $at",
                {"ref": f"norm-w{w}-{i}", "at": (center_day * DAY) + i},
            )

    # In recent 90 days, keeper performs 9 actions (9 / 10 = 0.9 > 0.5)
    for i in range(9):
        client.query(
            g,
            "MATCH (k:Actor {hid: 'K'}) CREATE (k)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) "
            "SET d.at = $at",
            {"ref": f"recent-norm-{i}", "at": (950 * DAY) + i},
        )

    res = pressure.pressure(client, org, T)
    assert res.status == NOT_FIRED
    assert "keepers' activity in last 90 days (9) was > 50%" in res.reason
    assert "default chosen for submission, not final" in res.reason
    assert res.evidence["keeper_condition_met"] is False
    assert res.evidence["keeper_activity_recent"] == 9


def test_pressure_condition2_no_keeper_record_not_computed(client, org):
    """Condition (1) met, but no keeper record exists -> NOT_COMPUTED with OPEN_REASON."""
    setup_low_actors(client, org)
    add_pressure_claims(client, org)

    res = pressure.pressure(client, org, T)
    assert res.status == NOT_COMPUTED
    assert "keeper activity condition open in freeze" in res.reason
    assert res.evidence["keeper_condition_default"] == "default chosen for submission, not final"


# ==============================================================================
# 2. Vouch & Claims Writing Tests
# ==============================================================================


def test_claim_writer_populates_target_hid_from_claim(client, org):
    """Writer populates Claim.target_hid when explicit in claim payload."""
    g = sc.graph_for(org)
    entries = [
        {
            "message_id": "m1",
            "date_utc": "2022-03-01T12:00:00Z",
            "author_hash": "author_a",
            "claims": [
                {
                    "kind": "VOUCH",
                    "target_hid": "candidate_c",
                    "quote": "I strongly vouch for candidate_c",
                    "confidence": 0.9,
                }
            ],
        }
    ]
    res = graph_write.write_claims(client, g, entries)
    assert res["claims_written"] == 1

    row = client.query(
        g, "MATCH (c:Claim {kind: 'VOUCH'}) RETURN c.target_hid, c.id LIMIT 1"
    ).result_set[0]
    assert row[0] == "candidate_c"


def test_claim_writer_populates_target_hid_from_text_fallback(client, org):
    """Writer extracts candidate target from quote/summary if not explicit."""
    g = sc.graph_for(org)
    entries = [
        {
            "message_id": "m2",
            "date_utc": "2022-03-01T12:00:00Z",
            "author_hash": "author_b",
            "summary": "email discussion regarding maintainer nomination",
            "claims": [
                {
                    "kind": "VOUCH",
                    "quote": "Please give commit rights to Rowan as they are ready",
                    "confidence": 0.8,
                }
            ],
        }
    ]
    res = graph_write.write_claims(client, g, entries)
    assert res["claims_written"] == 1

    row = client.query(g, "MATCH (c:Claim {kind: 'VOUCH'}) RETURN c.target_hid LIMIT 1").result_set[
        0
    ]
    assert row[0] == "Rowan"


def test_build_shares_edges_creation_window_and_domain_hash(client, org):
    """build_shares_edges creates creation_window and domain_hash edges."""
    g = sc.graph_for(org)
    # A and B first seen 2 days apart, and share same domain_hash
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human', domain_hash: 'corp_dom', "
        "first_seen_in_org: $t1}) "
        "MERGE (b:Actor {hid: 'B', kind: 'human', domain_hash: 'corp_dom', "
        "first_seen_in_org: $t2})",
        {"t1": 900 * DAY, "t2": 902 * DAY},
    )

    counts = shares.build_shares_edges(client, g, T)
    assert counts["creation_window"] == 2  # Bidirectional A->B, B->A
    assert counts["domain_hash"] == 2

    edges = client.query(
        g,
        "MATCH (a:Actor {hid: 'A'})-[s:SHARES]->(b:Actor {hid: 'B'}) "
        "RETURN s.signal ORDER BY s.signal",
    ).result_set
    signals = [e[0] for e in edges]
    assert signals == ["creation_window", "domain_hash"]


def test_build_shares_edges_only_interacts_with_target_and_burst(client, org):
    """build_shares_edges creates only_interacts_with_target and same_thread_burst."""
    g = sc.graph_for(org)
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human', first_seen_in_org: $t1}) "
        "MERGE (b:Actor {hid: 'B', kind: 'human', first_seen_in_org: $t2})",
        {"t1": 100 * DAY, "t2": 200 * DAY},
    )
    # Both vouch for target 'candidate_xyz' within 1 hour (same_thread_burst <= 48h)
    client.query(
        g,
        "MATCH (a:Actor {hid: 'A'}) CREATE (a)-[:ASSERTED]->"
        "(:Claim {id: 'c1', kind: 'VOUCH', at: 900 * 86400, target_hid: 'candidate_xyz'})",
    )
    client.query(
        g,
        "MATCH (b:Actor {hid: 'B'}) CREATE (b)-[:ASSERTED]->"
        "(:Claim {id: 'c2', kind: 'VOUCH', at: (900 * 86400) + 3600, target_hid: 'candidate_xyz'})",
    )

    counts = shares.build_shares_edges(client, g, T)
    assert counts["only_interacts_with_target"] == 2
    assert counts["same_thread_burst"] == 2


def test_vouch_fires_end_to_end_with_shares_edges_and_target_hid(client, org):
    """Vouch detector fires on real graph when vouchers target candidate and share >= 2 signals."""
    g = sc.graph_for(org)
    setup_low_actors(client, org)

    # A and B vouch for candidate C
    client.query(
        g,
        "MATCH (a:Actor {hid: 'A'}) CREATE (a)-[:ASSERTED]->"
        "(:Claim {id: 'v1', kind: 'VOUCH', at: 900 * 86400, target_hid: 'C'})",
    )
    client.query(
        g,
        "MATCH (b:Actor {hid: 'B'}) CREATE (b)-[:ASSERTED]->"
        "(:Claim {id: 'v2', kind: 'VOUCH', at: 905 * 86400, target_hid: 'C'})",
    )

    # Add domain_hash property so build_shares_edges generates multiple signals
    client.query(
        g,
        "MATCH (a:Actor {hid: 'A'}), (b:Actor {hid: 'B'}) "
        "SET a.domain_hash = 'dom123', b.domain_hash = 'dom123'",
    )

    # Run automated SHARES edge builder
    counts = shares.build_shares_edges(client, g, T)
    assert counts["total"] >= 4  # creation_window, domain_hash, only_interacts_with_target

    res = vouch.vouch(client, org, T)
    assert res.status == FIRED
    assert res.evidence["component_size"] == 2
    assert len(res.evidence["signal_types"]) >= 2
    assert "creation_window" in res.evidence["signal_types"]


# ==============================================================================
# 3. Lone Keeper Betweenness Fallback Tests
# ==============================================================================


def test_lone_keeper_fallback_flag_set_when_betweenness_ge_half(client, org):
    """When maxFlow fails/fallback forced, betweenness >= 0.5 sets lone keeper flag."""
    g = sc.graph_for(org)
    # Build star/bridge review graph where Keeper K is intermediate on all paths:
    # A -> K -> B (n = 3, raw score of K = 1.0, norm score = 1.0 / ((3-1)*(3-2)) = 0.5)
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human'}) "
        "MERGE (k:Actor {hid: 'K', kind: 'human'}) "
        "MERGE (b:Actor {hid: 'B', kind: 'human'}) "
        "CREATE (a)-[:REVIEWED {at: 100 * 86400}]->(k) "
        "CREATE (k)-[:REVIEWED {at: 100 * 86400}]->(b)",
    )

    res = lone_keeper.lone_keeper(client, org, "release", T, force_fallback=True)
    assert res.flag is True
    assert res.status == lone_keeper.FLAG_SET
    assert "betweenness >= 0.5 (fallback)" in res.reason
    assert res.evidence["betweenness_score"] >= 0.5
    assert res.evidence["betweenness_top_actor"] == "K"
    assert res.evidence["betweenness_ge_half"] is True


def test_lone_keeper_fallback_flag_not_set_when_betweenness_lt_half(client, org):
    """When betweenness < 0.5 and active keepers != 1, lone keeper flag is not set."""
    g = sc.graph_for(org)
    # A and B mutually review each other (n = 2, betweenness = 0.0)
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human'}) "
        "MERGE (b:Actor {hid: 'B', kind: 'human'}) "
        "CREATE (a)-[:REVIEWED {at: 100 * 86400}]->(b) "
        "CREATE (b)-[:REVIEWED {at: 100 * 86400}]->(a)",
    )

    res = lone_keeper.lone_keeper(client, org, "release", T, force_fallback=True)
    assert res.flag is False
    assert res.status == lone_keeper.FLAG_NOT_SET
    assert "betweenness < 0.5 (fallback)" in res.reason
    assert res.evidence["betweenness_score"] < 0.5
    assert res.evidence["betweenness_ge_half"] is False


def test_lone_keeper_fallback_not_computed_without_review_graph(client, org):
    """When no approval or review graph exists, fallback returns NOT_COMPUTED."""
    res = lone_keeper.lone_keeper(client, org, "release", T, force_fallback=True)
    assert res.status == NOT_COMPUTED
    assert "guardians not computed" in res.reason
    assert res.flag is None
    assert res.evidence == {}


def test_betweenness_fallback_direct_calculation(client, org):
    """Direct verification of betweenness_fallback calculation."""
    g = sc.graph_for(org)
    # Chain: A -> B -> C -> D
    # Nodes = 4, (n-1)*(n-2) = 3*2 = 6
    # Paths:
    # A->C via B
    # A->D via B, C
    # B->D via C
    # B lies on A->C (1) and A->D (1) = 2. Norm = 2/6 = 0.333
    # C lies on A->D (1) and B->D (1) = 2. Norm = 2/6 = 0.333
    client.query(
        g,
        "MERGE (a:Actor {hid: 'A', kind: 'human'}) "
        "MERGE (b:Actor {hid: 'B', kind: 'human'}) "
        "MERGE (c:Actor {hid: 'C', kind: 'human'}) "
        "MERGE (d:Actor {hid: 'D', kind: 'human'}) "
        "CREATE (a)-[:REVIEWED {at: 100 * 86400}]->(b) "
        "CREATE (b)-[:REVIEWED {at: 100 * 86400}]->(c) "
        "CREATE (c)-[:REVIEWED {at: 100 * 86400}]->(d)",
    )

    score, top_actor, queries = lone_keeper.betweenness_fallback(client, org, T)
    assert score is not None
    assert pytest.approx(score, abs=1e-2) == 2.0 / 6.0
    assert top_actor in ("B", "C")
    assert len(queries) >= 2
