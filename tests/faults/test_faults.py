"""Every failure type, including LLM offline, ends in a bounded HOLD (docs/HEARTHGUARD.md 8.4)."""

import pytest

from core.agents.guardrails import FailureType
from eval import faults


@pytest.fixture(scope="module")
def result():
    return faults.run()


def test_every_failure_type_was_injected(result):
    assert result["all_types_injected"]
    assert {f["failure_type"] for f in result["failures"]} == {str(f) for f in FailureType}


def test_each_ends_in_a_bounded_hold_with_no_llm_call_and_working_detectors(result):
    for f in result["failures"]:
        assert f["passed"], (f["failure_type"], f["checks"])


def test_circuit_breaker_suspends_the_plan(result):
    assert result["circuit_breaker"]["passed"], result["circuit_breaker"]


def test_llm_offline_holds_llm_tasks_while_structural_tasks_finish(result):
    assert result["mixed_board_llm_offline"]["passed"], result["mixed_board_llm_offline"]
