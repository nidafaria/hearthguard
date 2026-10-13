"""The deterministic filler (docs/decisions/0007). Pure: no LLM, no graph."""

import pytest

from core.learning import filler
from core.learning import templates as tp


@pytest.mark.parametrize(
    "reason, move, name",
    [
        ("these are our CI bots", "PRESSURE", "bots_are_not_newcomers"),
        ("dependabot and renovate are our bots", "PRESSURE", "bots_are_not_newcomers"),
        (
            "this was our announced handover to the company team",
            "VOUCH",
            "announced_handover_is_not_vouching",
        ),
        ("the vendor's contact changed", "RUSH", "vendor_contact_change_is_not_rush"),
    ],
)
def test_a_reason_selects_its_building_block(reason, move, name):
    p = filler.propose(reason)
    assert p.template is not None
    assert p.template.move == move
    assert p.template.exception == name
    assert p.attempts[0]["ok"] is True


def test_the_same_reason_always_gives_the_same_template():
    a = filler.propose("these are our CI bots").template.canonical()
    b = filler.propose("these are our CI bots").template.canonical()
    assert a == b


def test_the_owner_reason_is_not_copied_into_the_template():
    reason = "these are our CI bots, call them Rowan-bot"
    t = filler.propose(reason).template.canonical()
    assert "Rowan" not in str(t)
    assert reason not in str(t)


def test_a_reason_with_no_building_block_gets_three_attempts_then_nothing():
    p = filler.propose("I just do not like this one")
    assert p.template is None
    assert len(p.attempts) == filler.MAX_ATTEMPTS
    assert all(a["ok"] is False for a in p.attempts)


def test_the_table_only_proposes_real_moves_and_never_bypass():
    for _words, move, clauses, name in filler.TABLE:
        t, err = tp.validate(
            {
                "exception": name,
                "applies_to": f"move.{move}",
                "when": " AND ".join(clauses),
                "effect": tp.EFFECT,
            }
        )
        assert err is None, name
        assert move != "BYPASS"
