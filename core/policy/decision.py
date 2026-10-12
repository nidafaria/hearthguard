"""Decision policy (docs/HEARTHGUARD.md §7.3, FROZEN). Pure functions. No graph, no LLM.

decide(e) is the spec's code, line for line, in the spec's order. It has exactly the spec's seven
`if` statements and no others. Lone keeper only sets `risk`; it is never a move.

Two things sit AROUND it, outside the frozen function:

  evidence_from_moves()   turns each detector's status into the inputs decide() reads:
                            FIRED                    -> in `fired`
                            NOT_FIRED                -> nothing
                            NOT_COMPUTED             -> `unknown_moves` (neither fired nor not)
                            HOLD_READER_UNAVAILABLE  -> `missing_required` (Pressure and Vouch only)
  decide_with_unknowns()  PROPOSED, NOT IN THE SPEC (docs/decisions/0002-decision-unknowns.md).
                          If decide() would return NO_ACTION but a move is unknown, it returns
                          HOLD("move unknown: <names>") instead, so "we could not look" is never
                          reported as "nothing found".
"""

from dataclasses import dataclass, field, replace
from typing import Any

MOVES: tuple[str, ...] = ("PRESSURE", "VOUCH", "RUSH", "BYPASS")
READER_MOVES = frozenset({"PRESSURE", "VOUCH"})  # the two moves that need the LLM reader

FIRED = "FIRED"
NOT_FIRED = "NOT_FIRED"
NOT_COMPUTED = "NOT_COMPUTED"
HOLD_READER_UNAVAILABLE = "HOLD_READER_UNAVAILABLE"
MOVE_STATUSES = frozenset({FIRED, NOT_FIRED, NOT_COMPUTED, HOLD_READER_UNAVAILABLE})


# ----------------------------------------------------------------------------- typed results
@dataclass(frozen=True)
class HOLD:
    reason: str
    breakdown: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class SUPPRESS:
    owner_decision_ref: str | None
    breakdown: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class NOTE:
    pattern: str
    urgency: str
    breakdown: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class WATCH:
    moves: frozenset
    explain: bool = True
    breakdown: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class NO_ACTION:
    explain: Any = None  # the spec passes e.breakdown
    breakdown: dict = field(default_factory=dict, compare=False)


# ----------------------------------------------------------------------------- the evidence
@dataclass
class Evidence:
    """The `e` that decide() reads."""

    fired: frozenset = frozenset()  # subset of MOVES
    lone_keeper: bool = False  # guardians == 1 or active_keepers == 1
    missing_required: list = field(default_factory=list)
    open_objections: list = field(default_factory=list)
    covered_by_owner_decision: bool = False
    owner_decision_ref: str | None = None
    breakdown: dict = field(default_factory=dict)
    # Read ONLY by decide_with_unknowns() and the trace. decide() never branches on them.
    unknown_moves: tuple = ()
    lone_keeper_unknown: bool = False


def _trace(e: Evidence, rule: str) -> dict:
    """What decide() looked at and which rule returned. Information only."""
    risk = 1.5 if e.lone_keeper else 1.0
    return {
        **e.breakdown,
        "rule": rule,
        "fired": [m for m in MOVES if m in e.fired],
        "lone_keeper": e.lone_keeper,
        "risk": risk,
        "risk_x_moves": risk * len(e.fired),
        "unknown_moves": list(e.unknown_moves),
        "lone_keeper_unknown": e.lone_keeper_unknown,
    }


def _out(result, e: Evidence, rule: str):
    return replace(result, breakdown=_trace(e, rule))


# ----------------------------------------------------------------------------- the frozen policy
def decide(e: Evidence):
    if e.missing_required:
        return _out(HOLD(f"missing evidence: {e.missing_required}"), e, "missing_required")
    if e.open_objections:
        return _out(HOLD("skeptic objection open"), e, "open_objections")
    if e.covered_by_owner_decision:
        return _out(SUPPRESS(e.owner_decision_ref), e, "covered_by_owner_decision")
    moves = e.fired  # subset of {PRESSURE, VOUCH, RUSH, BYPASS}
    risk = 1.5 if e.lone_keeper else 1.0  # lone_keeper := guardians == 1 or active_keepers == 1
    if "BYPASS" in moves:
        return _out(NOTE(pattern="path-bypass", urgency="high"), e, "bypass")
    if len(moves) >= 2 and risk * len(moves) >= 3.0:
        return _out(NOTE(pattern="takeover-moves", urgency="high"), e, "moves_risk_high")
    if len(moves) >= 2:
        return _out(NOTE(pattern="takeover-moves", urgency="medium"), e, "moves_medium")
    if len(moves) == 1 and e.lone_keeper:
        return _out(WATCH(moves=moves, explain=True), e, "one_move_lone_keeper")
    return _out(NO_ACTION(explain=e.breakdown), e, "no_action")


# ----------------------------------------------------------------------------- PROPOSED layer
def decide_with_unknowns(e: Evidence):
    """decide(), plus the PROPOSED unknown-input handling (decisions/0002-decision-unknowns.md).

    NOT IN THE SPEC. It changes only a NO_ACTION result:
      - some move is unknown            -> HOLD("move unknown: <names in spec order>")
      - else exactly one move fired and lone_keeper is unknown (the one case where the multiplier
        decides between WATCH and NO_ACTION) -> HOLD("input unknown: LONE_KEEPER")
    Every other result, including every NOTE and WATCH, is returned exactly as decide() gives it.
    """
    result = decide(e)
    if isinstance(result, NO_ACTION):
        if e.unknown_moves:
            names = ", ".join(m for m in MOVES if m in e.unknown_moves)
            return _hold_from_no_action(result, f"move unknown: {names}")
        if e.lone_keeper_unknown and len(e.fired) == 1:
            return _hold_from_no_action(result, "input unknown: LONE_KEEPER")
    return result


def _hold_from_no_action(result: NO_ACTION, reason: str) -> HOLD:
    return HOLD(
        reason,
        breakdown={
            **result.breakdown,
            "rule": "unknown_input (PROPOSED 0002)",
            "frozen_result": "NO_ACTION",
        },
    )


# ------------------------------------------------------------------- building the evidence
def evidence_from_moves(
    statuses: dict[str, str],
    lone_keeper: bool | None,
    *,
    missing_required: tuple | list = (),
    open_objections: tuple | list = (),
    owner_decision_ref: str | None = None,
    breakdown: dict | None = None,
) -> Evidence:
    """Build decide()'s input from per-move statuses. Moves not listed count as NOT_FIRED.

    `lone_keeper` is True, False, or None (unknown). Unknown is passed on as False, because
    decide() needs a bool, and is recorded in `lone_keeper_unknown`.
    A reader-unavailable Pressure or Vouch becomes a missing input, never "not fired".
    """
    for move, status in statuses.items():
        if move not in MOVES:
            raise ValueError(
                f"{move!r} is not a move; expected one of {MOVES}. Lone keeper is not a move."
            )
        if status not in MOVE_STATUSES:
            raise ValueError(f"unknown status {status!r} for {move}")
        if status == HOLD_READER_UNAVAILABLE and move not in READER_MOVES:
            raise ValueError(f"only Pressure and Vouch need the reader; got {move}")

    fired = frozenset(m for m in MOVES if statuses.get(m) == FIRED)
    unknown = tuple(m for m in MOVES if statuses.get(m) == NOT_COMPUTED)
    reader_down = [
        f"{m}: reader unavailable" for m in MOVES if statuses.get(m) == HOLD_READER_UNAVAILABLE
    ]
    return Evidence(
        fired=fired,
        lone_keeper=bool(lone_keeper),
        missing_required=[*missing_required, *reader_down],
        open_objections=list(open_objections),
        covered_by_owner_decision=owner_decision_ref is not None,
        owner_decision_ref=owner_decision_ref,
        breakdown=dict(breakdown or {}),
        unknown_moves=unknown,
        lone_keeper_unknown=lone_keeper is None,
    )
