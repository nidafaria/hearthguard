"""Zero duplicate claims and zero duplicate notes under racing writers (docs/HEARTHGUARD.md 8.2)."""

from eval import race


def test_no_duplicate_claims_notes_or_step_numbers():
    r = race.run(workers=6, tasks=60, findings=15)
    assert r["claims"]["duplicate_claims"] == 0
    assert (
        r["notes"]["notes_in_graph"] == r["notes"]["expected"] == r["notes"]["sends_reported_true"]
    )
    assert r["agent_steps"]["seqs_unique_and_contiguous"]
    assert r["passed"]
