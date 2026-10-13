"""The four safety rules (docs/HEARTHGUARD.md 8.3, step 3). Pure."""

from core.learning import safety
from core.learning import templates as tp


def _t(applies_to="move.PRESSURE", when="actor.kind == 'bot' AND actor.hid IN org.declared_bots"):
    t, err = tp.validate(
        {
            "exception": "bots_are_not_newcomers",
            "applies_to": applies_to,
            "when": when,
            "effect": tp.EFFECT,
        }
    )
    assert err is None, err
    return t


def test_a_pressure_exception_with_a_declared_list_has_no_violation():
    assert safety.violations(_t()) == []


def test_it_may_never_narrow_bypass():
    v = safety.violations(_t(applies_to="move.BYPASS"))
    assert any("Bypass" in x for x in v)


def test_it_names_a_concrete_checkable_condition():
    # Schema refuses a `when` with no declared list, so the safety check is exercised on a
    # template built directly, the way a later schema change could let one through.
    t = _t()
    t.when = "actor.kind == 'bot'"
    assert any("checkable" in x for x in safety.violations(t))


def test_it_carries_no_field_that_could_touch_cost_or_guardians():
    t = _t()
    assert set(t.canonical()) == {"exception", "applies_to", "when", "effect"}


def test_the_rules_are_named_for_the_result():
    assert len(safety.RULES) == 4
