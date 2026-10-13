"""The regression gate (docs/HEARTHGUARD.md 8.3, step 4). Pure: the frozen decision code, no graph.

The synthetic cases pin the rule. The saved-suite cases pin what the gate says on the real
block-C red-team file: the frozen code reproduces every saved decision, and the Pressure, Vouch
and Rush exceptions are each judged on that suite.
"""

import pytest

from core.learning import gate as gt
from core.learning import pipeline as pl
from core.learning import templates as tp
from core.learning.pipeline import SUITE
from core.policy.decision import FIRED, NOT_COMPUTED, NOT_FIRED


def _t(move: str) -> tp.ExceptionTemplate:
    t, err = tp.validate(
        {
            "exception": "bots_are_not_newcomers",
            "applies_to": f"move.{move}",
            "when": "actor.kind == 'bot' AND actor.hid IN org.declared_bots",
            "effect": tp.EFFECT,
        }
    )
    assert err is None
    return t


def _campaign(moves: dict, decision: str, lk: str = "FLAG_SET") -> dict:
    return {"points": [{"moves": moves, "lone_keeper": lk, "decision": decision}]}


def _all(status: str = NOT_FIRED, **over) -> dict:
    base = {m: status for m in ("PRESSURE", "VOUCH", "RUSH", "BYPASS")}
    return {**base, **over}


def test_a_campaign_caught_only_through_the_narrowed_move_is_lost_and_the_gate_refuses():
    # One move fired with the lone keeper flag: WATCH. Remove that move and it is NO_ACTION.
    campaigns = [_campaign(_all(PRESSURE=FIRED), "WATCH")]
    r = gt.run(campaigns, [], _t("PRESSURE"))
    assert r.baseline_matches_saved
    assert r.planted_caught_before == 1
    assert r.planted_lost == 1
    assert r.passed is False
    assert "lost" in r.reason


def test_a_campaign_caught_through_another_move_is_kept():
    # Pressure and Bypass fire: NOTE through Bypass. Narrowing Pressure does not lose it.
    campaigns = [_campaign(_all(PRESSURE=FIRED, BYPASS=FIRED), "NOTE")]
    r = gt.run(campaigns, [], _t("PRESSURE"))
    assert r.planted_lost == 0
    assert r.passed is True


def test_narrowing_bypass_would_lose_its_campaign_so_the_gate_refuses_it():
    # The safety rules refuse Bypass outright (safety.py). The gate would refuse it too.
    campaigns = [_campaign(_all(BYPASS=FIRED), "NOTE")]
    r = gt.run(campaigns, [], _t("BYPASS"))
    assert r.planted_lost == 1
    assert r.passed is False


def test_a_baseline_that_does_not_reproduce_the_saved_decision_refuses_to_pass():
    campaigns = [_campaign(_all(), "WATCH")]  # saved says WATCH; the moves give NO_ACTION
    r = gt.run(campaigns, [], _t("PRESSURE"))
    assert r.baseline_matches_saved is False
    assert r.passed is False
    assert "baseline" in r.reason


def test_a_real_case_detection_lost_refuses_to_pass():
    real = [{"moves": _all(PRESSURE=FIRED), "lone_keeper": "FLAG_SET"}]
    r = gt.run([], real, _t("PRESSURE"))
    assert r.real_lost == 1
    assert r.passed is False


def test_an_unknown_move_is_not_treated_as_not_fired():
    campaigns = [_campaign(_all(PRESSURE=NOT_COMPUTED), "HOLD")]
    r = gt.run(campaigns, [], _t("PRESSURE"))
    assert r.baseline_matches_saved  # HOLD: move unknown, as the frozen code reports
    assert r.planted_caught_before == 0


needs_suite = pytest.mark.skipif(
    not (pl.RESULTS / SUITE).exists(), reason="saved red-team suite absent"
)


@needs_suite
def test_the_saved_suite_replays_exactly_with_no_exception():
    campaigns, real = pl.load_suite()
    r = gt.run(campaigns, real, _t("PRESSURE"))
    assert r.baseline_matches_saved
    assert r.planted_total == 200
    assert r.planted_caught_before == 167  # summary.caught in redteam_xz.json


@needs_suite
def test_on_the_saved_suite_pressure_is_safe_but_vouch_and_rush_are_not():
    campaigns, real = pl.load_suite()
    pressure = gt.run(campaigns, real, _t("PRESSURE"))
    vouch = gt.run(campaigns, real, _t("VOUCH"))
    rush = gt.run(campaigns, real, _t("RUSH"))
    assert pressure.passed is True
    # PRESSURE never reaches FIRED in this suite (docs/decisions/0005), so narrowing it changes
    # nothing. That is why it passes; the shadow numbers say so.
    assert pressure.planted_points_changed == 0
    assert vouch.passed is False and vouch.planted_lost > 0
    assert rush.passed is False and rush.planted_lost > 0
