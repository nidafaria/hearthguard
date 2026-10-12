"""Decision policy (spec §7.3) and conflict policy (spec §7.2). Pure functions, no server.

The expected values come from tests/fixtures/decision_cases.py, which was committed before the
implementation. The oracle test runs the spec's own decide() code, taken from the spec text.
"""

import ast
import inspect
import itertools
from pathlib import Path

import pytest

from core.policy import conflict, decision
from core.policy.decision import (
    HOLD,
    MOVES,
    NO_ACTION,
    NOTE,
    SUPPRESS,
    WATCH,
    Evidence,
    decide,
    decide_with_unknowns,
    evidence_from_moves,
)
from tests.fixtures.decision_cases import (
    BAD_CONFLICT_INPUTS,
    CONFLICT_CASES,
    DECISION_CASES,
)

SPEC = Path(__file__).resolve().parents[2] / "docs" / "HEARTHGUARD.md"


def evidence(case) -> Evidence:
    return evidence_from_moves(
        case.moves,
        case.lone_keeper,
        missing_required=case.missing_required,
        open_objections=case.open_objections,
        owner_decision_ref=case.covered_by,
    )


def as_tuple(result) -> tuple:
    if isinstance(result, HOLD):
        return ("HOLD", result.reason)
    if isinstance(result, SUPPRESS):
        return ("SUPPRESS", result.owner_decision_ref)
    if isinstance(result, NOTE):
        return ("NOTE", result.pattern, result.urgency)
    if isinstance(result, WATCH):
        return ("WATCH", tuple(m for m in MOVES if m in result.moves))
    assert isinstance(result, NO_ACTION)
    return ("NO_ACTION",)


# ------------------------------------------------------------------ decision fixtures
@pytest.mark.parametrize("case", DECISION_CASES, ids=lambda c: c.name)
def test_decision_fixture_final_result(case):
    assert as_tuple(decide_with_unknowns(evidence(case))) == case.expected


@pytest.mark.parametrize("case", DECISION_CASES, ids=lambda c: c.name)
def test_decision_fixture_frozen_function_alone(case):
    # decide() alone never sees the unknown layer. Where the fixture says what it returns, it
    # must be that; elsewhere it is the same as the final result.
    assert as_tuple(decide(evidence(case))) == (case.frozen or case.expected)


@pytest.mark.parametrize("case", DECISION_CASES, ids=lambda c: c.name)
def test_every_result_carries_a_breakdown(case):
    for result in (decide(evidence(case)), decide_with_unknowns(evidence(case))):
        assert result.breakdown["rule"]
        assert {"fired", "risk", "risk_x_moves", "lone_keeper", "unknown_moves"} <= set(
            result.breakdown
        )


def test_lone_keeper_is_not_a_move():
    with pytest.raises(ValueError, match="not a move"):
        evidence_from_moves({"LONE_KEEPER": "FIRED"}, True)
    assert "LONE_KEEPER" not in MOVES


def test_reader_unavailable_only_for_pressure_and_vouch():
    with pytest.raises(ValueError, match="reader"):
        evidence_from_moves({"RUSH": "HOLD_READER_UNAVAILABLE"}, False)
    with pytest.raises(ValueError, match="unknown status"):
        evidence_from_moves({"RUSH": "MAYBE"}, False)


def test_reader_unavailable_is_a_missing_input_not_a_non_fire():
    both = evidence_from_moves(
        {"PRESSURE": "HOLD_READER_UNAVAILABLE", "VOUCH": "HOLD_READER_UNAVAILABLE"}, False
    )
    assert both.missing_required == ["PRESSURE: reader unavailable", "VOUCH: reader unavailable"]
    assert both.fired == frozenset() and both.unknown_moves == ()
    assert as_tuple(decide(both))[0] == "HOLD"


# ------------------------------------------------------------------ "exactly as written"
def spec_decide_source() -> str:
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("```python\ndef decide(e):")
    return text[start + len("```python\n") : text.index("```", start + 10)]


def spec_oracle():
    """The spec's own decide(), run with plain-tuple constructors."""
    ns = {
        "HOLD": lambda reason: ("HOLD", reason),
        "SUPPRESS": lambda ref: ("SUPPRESS", ref),
        "NOTE": lambda pattern, urgency: ("NOTE", pattern, urgency),
        "WATCH": lambda moves, explain: ("WATCH", tuple(m for m in MOVES if m in moves)),
        "NO_ACTION": lambda explain: ("NO_ACTION",),
    }
    exec(spec_decide_source(), ns)  # noqa: S102 (the spec text is the oracle)
    return ns["decide"]


def all_gate_combinations():
    subsets = [
        frozenset(m for m, on in zip(MOVES, bits, strict=True) if on)
        for bits in itertools.product([False, True], repeat=4)
    ]
    for fired, lone, miss, obj, cov in itertools.product(
        subsets, [False, True], [False, True], [False, True], [False, True]
    ):
        yield Evidence(
            fired=fired,
            lone_keeper=lone,
            missing_required=["x"] if miss else [],
            open_objections=["o"] if obj else [],
            covered_by_owner_decision=cov,
            owner_decision_ref="od-1" if cov else None,
        )


def test_decide_agrees_with_the_spec_code_on_every_input():
    oracle = spec_oracle()
    n = 0
    for e in all_gate_combinations():
        assert as_tuple(decide(e)) == oracle(e), e
        n += 1
    assert n == 16 * 2 * 2 * 2 * 2


def test_decide_has_exactly_the_specs_branches_and_reads_only_its_fields():
    tree = ast.parse(inspect.getsource(decide))
    assert sum(isinstance(n, ast.If) for n in ast.walk(tree)) == 7
    assert not any(isinstance(n, ast.For | ast.While) for n in ast.walk(tree))
    read = {
        n.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "e"
    }
    assert read == {
        "missing_required",
        "open_objections",
        "covered_by_owner_decision",
        "owner_decision_ref",
        "fired",
        "lone_keeper",
        "breakdown",
    }
    spec_tree = ast.parse(spec_decide_source())
    assert sum(isinstance(n, ast.If) for n in ast.walk(spec_tree)) == 7


# ------------------------------------------------------------------ property tests
ALL_STATUSES = ("FIRED", "NOT_FIRED", "NOT_COMPUTED", "HOLD_READER_UNAVAILABLE")


def all_status_vectors():
    for combo in itertools.product(ALL_STATUSES, repeat=4):
        statuses = dict(zip(MOVES, combo, strict=True))
        if any(
            s == "HOLD_READER_UNAVAILABLE" and m not in decision.READER_MOVES
            for m, s in statuses.items()
        ):
            continue
        for lone in (True, False, None):
            yield statuses, lone


def test_path_bypass_note_only_when_bypass_fired():
    checked = 0
    for statuses, lone in all_status_vectors():
        e = evidence_from_moves(statuses, lone)
        for fn in (decide, decide_with_unknowns):
            r = fn(e)
            if isinstance(r, NOTE) and r.pattern == "path-bypass":
                assert statuses["BYPASS"] == "FIRED"
            if statuses["BYPASS"] == "FIRED" and not e.missing_required:
                assert as_tuple(r) == ("NOTE", "path-bypass", "high")
        checked += 1
    # Pressure and Vouch take 4 statuses, Rush and Bypass 3: 4*4*3*3 = 144, times 3 lone values.
    assert checked == 432


def test_every_note_and_watch_is_backed_by_fired_moves():
    for statuses, lone in all_status_vectors():
        e = evidence_from_moves(statuses, lone)
        r = decide_with_unknowns(e)
        n = len(e.fired)
        if isinstance(r, NOTE) and r.pattern == "takeover-moves":
            assert n >= 2
            assert (r.urgency == "high") == ((1.5 if e.lone_keeper else 1.0) * n >= 3.0)
        if isinstance(r, WATCH):
            assert n == 1 and e.lone_keeper
        if n == 0 and not e.missing_required:
            assert isinstance(r, NO_ACTION | HOLD)


def test_an_unknown_move_is_never_counted_as_fired_or_as_not_fired():
    # Swapping NOT_COMPUTED for NOT_FIRED must change nothing, except that a NO_ACTION may become
    # a HOLD that names the unknown move. And it must never create or remove a fired move.
    for statuses, lone in all_status_vectors():
        for move in MOVES:
            if statuses[move] != "NOT_COMPUTED":
                continue
            as_unknown = evidence_from_moves(statuses, lone)
            as_quiet = evidence_from_moves({**statuses, move: "NOT_FIRED"}, lone)
            assert as_unknown.fired == as_quiet.fired
            a, b = decide_with_unknowns(as_unknown), decide_with_unknowns(as_quiet)
            if isinstance(a, HOLD) and a.reason.startswith("move unknown"):
                assert move in a.reason
                assert isinstance(decide(as_unknown), NO_ACTION)
            else:
                assert as_tuple(a) == as_tuple(b)


def test_the_proposed_layer_only_ever_changes_no_action():
    for statuses, lone in all_status_vectors():
        e = evidence_from_moves(statuses, lone)
        frozen, final = decide(e), decide_with_unknowns(e)
        if not isinstance(frozen, NO_ACTION):
            assert as_tuple(final) == as_tuple(frozen)
        elif as_tuple(final) != as_tuple(frozen):
            assert isinstance(final, HOLD) and "unknown" in final.reason


def test_without_unknowns_the_proposed_layer_changes_nothing():
    for e in all_gate_combinations():
        assert as_tuple(decide_with_unknowns(e)) == as_tuple(decide(e))


# ------------------------------------------------------------------ conflict policy
def claims_of(case):
    return tuple(conflict.Claim(**c) for c in case.claims)


@pytest.mark.parametrize("case", CONFLICT_CASES, ids=lambda c: c.name)
def test_conflict_fixture(case):
    res = conflict.resolve(claims_of(case))
    assert res.status == case.expected["status"]
    assert res.winner == case.expected["winner"]
    assert res.basis == case.expected["basis"]
    assert res.links == case.expected["links"]
    # Both claims are kept and named, in the order given. Nothing is deleted.
    assert res.claim_ids == tuple(c["id"] for c in case.claims)


@pytest.mark.parametrize("case", CONFLICT_CASES, ids=lambda c: c.name)
def test_no_winner_unless_resolved(case):
    res = conflict.resolve(claims_of(case))
    assert (res.winner is not None) == (res.status == conflict.RESOLVED)
    assert res.links[0][1] == "CONTRADICTS"


def test_authority_beats_time_for_every_pair_of_classes():
    order = conflict.AUTHORITY_ORDER
    for hi, lo in itertools.combinations(reversed(order), 2):
        for hi_at, lo_at in ((1, 999), (999, 1), (5, 5), (None, 7)):
            a = conflict.Claim("hi", hi, hi_at)
            b = conflict.Claim("lo", lo, lo_at)
            for pair in ((a, b), (b, a)):
                res = conflict.resolve(pair)
                assert (res.winner, res.basis, res.status) == ("hi", "authority", "RESOLVED")


def test_equal_authority_never_picks_a_winner_without_two_different_times():
    for source in conflict.AUTHORITY_ORDER:
        for t1, t2 in ((5, 5), (None, 5), (5, None), (None, None)):
            res = conflict.resolve(
                (conflict.Claim("c1", source, t1), conflict.Claim("c2", source, t2))
            )
            assert res.status == conflict.UNRESOLVED and res.winner is None


@pytest.mark.parametrize(
    "name,claims", BAD_CONFLICT_INPUTS, ids=[n for n, _ in BAD_CONFLICT_INPUTS]
)
def test_bad_conflict_inputs_are_refused(name, claims):
    with pytest.raises(ValueError):
        conflict.resolve(tuple(conflict.Claim(**c) for c in claims))


def test_two_claims_cannot_be_exceptions_to_each_other():
    with pytest.raises(ValueError, match="each be an exception"):
        conflict.resolve(
            (
                conflict.Claim("c1", "system_record", 1, exception_to="c2"),
                conflict.Claim("c2", "system_record", 2, exception_to="c1"),
            )
        )
