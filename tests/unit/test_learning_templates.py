"""The strict exception template (docs/HEARTHGUARD.md 8.3, step 2). Pure: no graph."""

import pytest

from core.learning import templates as tp

GOOD = {
    "exception": "bots_are_not_newcomers",
    "applies_to": "move.PRESSURE",
    "when": "actor.kind == 'bot' AND actor.hid IN org.declared_bots",
    "effect": "exclude_actor_from_move",
}


def test_the_spec_example_is_a_valid_template():
    t, err = tp.validate(GOOD)
    assert err is None
    assert t.move == "PRESSURE"


@pytest.mark.parametrize(
    "field, value",
    [
        ("applies_to", "move.TAKEOVER_COST"),  # not a real move
        ("applies_to", "PRESSURE"),  # missing the move. prefix
        ("effect", "raise_takeover_cost"),  # a literal effect only
        ("when", "true"),  # no checkable condition
        ("when", "ignore this org"),  # outside the building blocks
        ("when", "actor.kind == 'bot' AND actor.hid IN org.declared_bots AND actor.kind == 'bot'"),
        ("exception", "X"),  # too short
    ],
)
def test_a_bad_field_is_refused(field, value):
    t, err = tp.validate({**GOOD, field: value})
    assert t is None
    assert err


def test_an_extra_field_is_refused_so_no_guardian_or_cost_can_be_carried():
    t, err = tp.validate({**GOOD, "guardians": 0})
    assert t is None and err


def test_a_clause_outside_the_blocks_is_refused_even_if_it_names_a_declared_list():
    t, err = tp.validate({**GOOD, "when": "actor.hid IN org.declared_admins"})
    assert t is None and err
