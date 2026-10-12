"""Red Team generator: determinism, seed sensitivity, and bounds. No database.

Hand-worked expectations (written before the code was checked against them):
  - the same (n, seed, case) must produce identical canonical bytes, every time.
  - a different seed must produce a different list (the first campaign's patience or moves differ
    for at least one of the first ten campaigns; checked over ten seeds, not one).
  - every campaign has a non-empty move set drawn only from MOVES, and a patience drawn only from
    PATIENCE_LEVELS.
  - a campaign with PRESSURE or VOUCH has n_socks in {2,3,4}; without them n_socks is 0.
  - a campaign with BYPASS has bypass_props in {1,2,3}; without it, 0.
  - every event is synthetic-only: no real names; actors are roles (attacker, sock-k, newcomer).
  - a clean campaign has no move, no claim and no socks.
"""

import pytest

from redteam import generate as gen


def test_same_seed_same_bytes():
    a = gen.to_bytes(gen.generate(50, 7, "tallowdate"))
    b = gen.to_bytes(gen.generate(50, 7, "tallowdate"))
    assert a == b
    assert len(a) > 1000


def test_same_seed_same_bytes_clean():
    a = gen.to_bytes(gen.clean_campaigns(20, 7, "xz"))
    b = gen.to_bytes(gen.clean_campaigns(20, 7, "xz"))
    assert a == b


def test_different_seed_different_campaigns():
    differs = 0
    for seed in range(10):
        a = gen.generate(10, seed, "tallowdate")
        b = gen.generate(10, seed + 1000, "tallowdate")
        if [(c.moves, c.patience_days) for c in a] != [(c.moves, c.patience_days) for c in b]:
            differs += 1
    assert differs == 10


def test_prefix_is_stable_when_n_grows():
    small = gen.generate(5, 7, "tallowdate")
    big = gen.generate(20, 7, "tallowdate")
    assert gen.to_bytes(small[:5]) == gen.to_bytes(big[:5])


@pytest.mark.parametrize("case", gen.CASES)
def test_parameter_bounds(case):
    for c in gen.generate(60, 7, case):
        assert c.moves and set(c.moves) <= set(gen.MOVES)
        assert c.patience_days in gen.PATIENCE_LEVELS
        assert c.privilege in gen.PRIVILEGES
        if set(c.moves) & {"PRESSURE", "VOUCH"}:
            assert c.n_socks in (2, 3, 4)
            assert 1 <= len(c.sock_signals) <= 3
        else:
            assert c.n_socks == 0 and c.sock_signals == []
        if "BYPASS" in c.moves:
            assert c.bypass_props in (1, 2, 3)
            assert c.final_day == c.patience_days + c.release_delay_days
        else:
            assert c.bypass_props == 0


def test_event_roles_are_labels_not_names():
    allowed = {"attacker"} | {f"sock-{k}" for k in range(4)}
    for c in gen.generate(40, 3, "tallowdate"):
        assert {e.actor for e in c.events} <= allowed


def test_grant_and_release_times_follow_patience():
    # Hand check: a RUSH campaign with patience 90 grants at day 90 exactly.
    for c in gen.generate(80, 11, "tallowdate"):
        for e in c.events:
            if e.kind == "grant":
                assert e.day == c.patience_days


def test_clean_campaign_has_no_moves_or_socks():
    for c in gen.clean_campaigns(30, 7, "tallowdate"):
        assert c.clean and c.moves == []
        assert all(e.move is None and e.kind != "claim" for e in c.events)
        assert c.n_socks == 0
        assert {e.actor for e in c.events} == {"newcomer"}


def test_unknown_case_is_refused():
    with pytest.raises(ValueError):
        gen.generate(1, 1, "nope")


def test_campaign_ids_are_unique_and_labelled():
    ids = [c.id for c in gen.generate(200, 7, "tallowdate")]
    assert len(set(ids)) == 200
    assert all(i.startswith("rt-atk-tallowdate-s7-") for i in ids)


def test_baseline_check_records_a_match_and_a_mismatch():
    # Worked out first: xz baseline is 4679 nodes / 4668 edges, so those counts match and one
    # node fewer does not.
    from redteam import run

    ok = run.baseline_check("xz", {"nodes": 4679, "edges": 4668})
    assert ok["matches_saved_baseline"] is True
    bad = run.baseline_check("xz", {"nodes": 4678, "edges": 4668})
    assert bad["matches_saved_baseline"] is False
    assert bad["saved_baseline"] == {"nodes": 4679, "edges": 4668}
    assert "4669" not in run.case_label("xz")
