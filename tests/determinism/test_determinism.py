"""Same findings under 5 different task orderings (docs/HEARTHGUARD.md 8.2, 10.2)."""

from eval import verify_determinism


def test_findings_are_identical_under_five_orderings():
    r = verify_determinism.run(5)
    assert r["findings_identical_across_orderings"]
    assert r["distinct_claim_orders"] == 5  # the order did differ
    assert all(r["findings_match_fixture_answers"].values())
    assert r["passed"]
