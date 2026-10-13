"""The four end states (docs/HEARTHGUARD.md 8.3, step 5). Pure."""

from core.learning import gate as gt
from core.learning import states as st


def _gate(passed=True, lost=0):
    return gt.GateResult(
        passed=passed,
        reason="ok" if passed else "1 planted campaign(s) lost",
        baseline_matches_saved=True,
        planted_total=200,
        planted_caught_before=167,
        planted_caught_after=167 - lost,
        planted_lost=lost,
        planted_points_changed=0,
        real_total=22,
        real_lost=0,
        real_points_changed=0,
    )


def _state(**kw):
    base = dict(proposed=True, violations=[], gate=_gate(), agreements=1, owner_approved=False)
    return st.end_state(**{**base, **kw})


def test_no_building_block_means_human_review():
    assert _state(proposed=False, gate=None)[0] == st.HUMAN_REVIEW


def test_a_safety_violation_means_rejected_and_says_why():
    s, why = _state(violations=["never narrows Bypass"], gate=None)
    assert s == st.REJECTED
    assert "Bypass" in why


def test_a_lost_detection_means_rejected():
    s, why = _state(gate=_gate(passed=False, lost=3))
    assert s == st.REJECTED
    assert "lost" in why


def test_a_gate_pass_is_shadow_until_agreements_or_owner_approval():
    assert _state()[0] == st.SHADOW
    assert _state(agreements=st.K_AGREEMENTS - 1)[0] == st.SHADOW


def test_k_independent_agreements_adopt():
    assert _state(agreements=st.K_AGREEMENTS)[0] == st.ADOPTED


def test_owner_approval_adopts_after_a_pass():
    assert _state(owner_approved=True)[0] == st.ADOPTED


def test_owner_approval_cannot_adopt_what_failed_the_gate():
    assert _state(owner_approved=True, gate=_gate(passed=False, lost=1))[0] == st.REJECTED


def test_every_state_is_one_of_the_four():
    assert set(st.STATES) == {st.ADOPTED, st.SHADOW, st.HUMAN_REVIEW, st.REJECTED}
