"""Expected results for the decision policy (spec §7.3) and the conflict policy (spec §7.2).

THIS FILE WAS WRITTEN BEFORE THE IMPLEMENTATION and committed first. It is plain data on purpose:
it imports nothing from core/, so it can exist before core/policy/ does. Every expected result is
derived by hand from the frozen spec text below. If the code later disagrees with a derivation,
the code is wrong, not this file.

------------------------------------------------------------------------------------------------
Spec §7.3, the frozen decide(), in order:
  1. if missing_required:            HOLD(f"missing evidence: {missing_required}")
  2. if open_objections:             HOLD("skeptic objection open")
  3. if covered_by_owner_decision:   SUPPRESS(owner_decision_ref)
  4. moves = fired;  risk = 1.5 if lone_keeper else 1.0
  5. if "BYPASS" in moves:           NOTE(path-bypass, high)
  6. if len(moves) >= 2 and risk * len(moves) >= 3.0:   NOTE(takeover-moves, high)
  7. if len(moves) >= 2:             NOTE(takeover-moves, medium)
  8. if len(moves) == 1 and lone_keeper:                WATCH(moves)
  9. otherwise:                      NO_ACTION
missing_required is a list, so its text in the reason is the Python list text: ['a', 'b'].

Inputs per move are one of:
  FIRED, NOT_FIRED                  -> the move is in `fired` or it is not
  NOT_COMPUTED                      -> unknown. Never counted as fired and never as not fired.
  HOLD_READER_UNAVAILABLE           -> Pressure or Vouch only. Passed as a MISSING INPUT (rule 1),
                                       not as "not fired".
A move that a case does not list is NOT_FIRED. lone_keeper is True, False, or None (unknown).

PROPOSED layer (docs/decisions/0002-decision-unknowns.md), applied AFTER the frozen decide():
  - frozen result is NO_ACTION and some move is unknown -> HOLD("move unknown: <names>"), names in
    the order PRESSURE, VOUCH, RUSH, BYPASS, joined by ", ".
  - else frozen result is NO_ACTION, exactly one move fired, and lone_keeper is unknown (that is
    the one case where lone_keeper decides between WATCH and NO_ACTION)
    -> HOLD("input unknown: LONE_KEEPER").
  - anything else is returned unchanged.
Cases with `frozen` set show what the frozen decide() alone returns; `expected` is the final answer.
------------------------------------------------------------------------------------------------
Spec §7.2, the conflict policy, in order:
  1. Authority: owner decision > system record > established actor > low-history actor > hearsay.
  2. Specificity: an explicit exception narrows a general statement.
  3. Recency: the newer claim wins between equals.
  4. UNRESOLVED: equal authority and still conflicting. Never pick a winner.
Read in that order, recency separates every equal-authority pair that has two different times, so
UNRESOLVED arises when the times are equal or one is missing. Both claims are always kept.
Links: every result links CONTRADICTS (first claim -> second claim). A recency win adds
(winner SUPERSEDES loser). A narrowing adds (exception QUALIFIES general).
"""

from dataclasses import dataclass, field

MOVES = ("PRESSURE", "VOUCH", "RUSH", "BYPASS")


@dataclass(frozen=True)
class DecisionCase:
    name: str
    expected: tuple  # ("HOLD", reason) | ("SUPPRESS", ref) | ("NOTE", pattern, urgency)
    #                  | ("WATCH", moves) | ("NO_ACTION",)
    moves: dict = field(default_factory=dict)  # move -> status; unlisted moves are NOT_FIRED
    lone_keeper: bool | None = False
    missing_required: tuple = ()
    open_objections: tuple = ()
    covered_by: str | None = None
    frozen: tuple | None = None  # what the frozen decide() alone returns, if it differs


DECISION_CASES: tuple[DecisionCase, ...] = (
    # a. BYPASS fired alone, no multiplier. Rules 1-3 do not apply. Rule 5: BYPASS in moves.
    DecisionCase("a_bypass_alone", ("NOTE", "path-bypass", "high"), {"BYPASS": "FIRED"}),
    # b. PRESSURE + VOUCH, lone keeper false. risk 1.0. Rule 6: 1.0 * 2 = 2.0 < 3.0, no.
    #    Rule 7: two moves. NOTE(takeover-moves, medium).
    DecisionCase(
        "b_two_moves_not_lone",
        ("NOTE", "takeover-moves", "medium"),
        {"PRESSURE": "FIRED", "VOUCH": "FIRED"},
        lone_keeper=False,
    ),
    # c. Same two moves, lone keeper true. risk 1.5. Rule 6: 1.5 * 2 = 3.0 >= 3.0, yes (the
    #    boundary counts). NOTE(takeover-moves, high).
    DecisionCase(
        "c_two_moves_lone",
        ("NOTE", "takeover-moves", "high"),
        {"PRESSURE": "FIRED", "VOUCH": "FIRED"},
        lone_keeper=True,
    ),
    # d. PRESSURE alone, lone keeper true. Rules 5-7 need BYPASS or two moves. Rule 8: one move and
    #    lone keeper. WATCH(PRESSURE).
    DecisionCase(
        "d_one_move_lone", ("WATCH", ("PRESSURE",)), {"PRESSURE": "FIRED"}, lone_keeper=True
    ),
    # e. PRESSURE alone, lone keeper false. Rule 8 needs lone keeper. Rule 9: NO_ACTION.
    DecisionCase("e_one_move_not_lone", ("NO_ACTION",), {"PRESSURE": "FIRED"}, lone_keeper=False),
    # f. RUSH + BYPASS. Rule 5 comes before the two-move rules and BYPASS is in moves:
    #    NOTE(path-bypass, high), not takeover-moves, whatever the multiplier.
    DecisionCase(
        "f_rush_and_bypass",
        ("NOTE", "path-bypass", "high"),
        {"RUSH": "FIRED", "BYPASS": "FIRED"},
        lone_keeper=False,
    ),
    # g. Open objection with PRESSURE + VOUCH. Rule 1 passes (nothing missing). Rule 2: an
    #    objection is open. HOLD("skeptic objection open"), before any move is looked at.
    DecisionCase(
        "g_open_objection",
        ("HOLD", "skeptic objection open"),
        {"PRESSURE": "FIRED", "VOUCH": "FIRED"},
        open_objections=("obj-1",),
    ),
    # h. Covered by an owner decision, with BYPASS fired. Rule 3 comes before rule 5:
    #    SUPPRESS("od-17"). The owner's earlier decision wins over the move.
    DecisionCase(
        "h_covered_by_owner",
        ("SUPPRESS", "od-17"),
        {"BYPASS": "FIRED"},
        covered_by="od-17",
    ),
    # i. Required evidence is missing. Rule 1: HOLD(f"missing evidence: ['release provenance']").
    DecisionCase(
        "i_missing_required",
        ("HOLD", "missing evidence: ['release provenance']"),
        {"PRESSURE": "FIRED", "VOUCH": "FIRED"},
        missing_required=("release provenance",),
    ),
    # j. Pressure could not run (reader unavailable), Rush fired, lone keeper true.
    #    Task rule: a reader-unavailable Pressure is a MISSING INPUT, not "not fired". So
    #    missing_required = ["PRESSURE: reader unavailable"] and rule 1 returns first:
    #    HOLD("missing evidence: ['PRESSURE: reader unavailable']").
    #    (If Pressure were wrongly counted as "not fired", rules 5-8 would give RUSH alone with
    #    risk 1.5 -> WATCH(RUSH). That is exactly the mistake the missing-input rule prevents.)
    DecisionCase(
        "j_reader_unavailable",
        ("HOLD", "missing evidence: ['PRESSURE: reader unavailable']"),
        {"PRESSURE": "HOLD_READER_UNAVAILABLE", "RUSH": "FIRED"},
        lone_keeper=True,
    ),
    # k. Bypass is NOT_COMPUTED, no other move fired, lone keeper false. Frozen decide(): moves
    #    is empty, rule 9, NO_ACTION. Proposed layer: NO_ACTION and BYPASS unknown ->
    #    HOLD("move unknown: BYPASS").
    DecisionCase(
        "k_unknown_bypass",
        ("HOLD", "move unknown: BYPASS"),
        {"BYPASS": "NOT_COMPUTED"},
        lone_keeper=False,
        frozen=("NO_ACTION",),
    ),
    # --- extra cases, derived the same way ---
    # n. BYPASS unknown, but PRESSURE + VOUCH fired, lone false. Frozen: 2.0 < 3.0, rule 7,
    #    NOTE(takeover-moves, medium). Not NO_ACTION, so the proposed layer leaves it alone.
    DecisionCase(
        "n_unknown_move_does_not_override_a_note",
        ("NOTE", "takeover-moves", "medium"),
        {"BYPASS": "NOT_COMPUTED", "PRESSURE": "FIRED", "VOUCH": "FIRED"},
        lone_keeper=False,
    ),
    # o. RUSH unknown, PRESSURE alone fired, lone true. Frozen: rule 8, WATCH(PRESSURE).
    #    Not NO_ACTION, so unchanged.
    DecisionCase(
        "o_unknown_move_does_not_override_a_watch",
        ("WATCH", ("PRESSURE",)),
        {"RUSH": "NOT_COMPUTED", "PRESSURE": "FIRED"},
        lone_keeper=True,
    ),
    # p. VOUCH unknown, nothing fired, lone false. Frozen: NO_ACTION. Layer: HOLD VOUCH.
    DecisionCase(
        "p_unknown_vouch",
        ("HOLD", "move unknown: VOUCH"),
        {"VOUCH": "NOT_COMPUTED"},
        lone_keeper=False,
        frozen=("NO_ACTION",),
    ),
    # q. VOUCH and BYPASS unknown, nothing fired. Frozen: NO_ACTION. Layer lists both, in the
    #    order PRESSURE, VOUCH, RUSH, BYPASS: "move unknown: VOUCH, BYPASS".
    DecisionCase(
        "q_two_unknown_moves",
        ("HOLD", "move unknown: VOUCH, BYPASS"),
        {"VOUCH": "NOT_COMPUTED", "BYPASS": "NOT_COMPUTED"},
        lone_keeper=False,
        frozen=("NO_ACTION",),
    ),
    # r. Lone keeper unknown (None), PRESSURE alone fired. The frozen function needs a bool, so
    #    unknown is passed as False: rule 9, NO_ACTION. This is the one case where the unknown
    #    multiplier decides (with lone true it would be WATCH). Layer: HOLD("input unknown:
    #    LONE_KEEPER").
    DecisionCase(
        "r_unknown_lone_keeper_decides",
        ("HOLD", "input unknown: LONE_KEEPER"),
        {"PRESSURE": "FIRED"},
        lone_keeper=None,
        frozen=("NO_ACTION",),
    ),
    # s. Lone keeper unknown, nothing fired. With no move the multiplier cannot matter: NO_ACTION.
    DecisionCase("s_unknown_lone_keeper_irrelevant", ("NO_ACTION",), {}, lone_keeper=None),
    # t. Lone keeper unknown, PRESSURE + VOUCH fired. Passed as False: 2.0 < 3.0, rule 7,
    #    NOTE(takeover-moves, medium). A note is still sent, so the layer leaves it alone.
    DecisionCase(
        "t_unknown_lone_keeper_with_two_moves",
        ("NOTE", "takeover-moves", "medium"),
        {"PRESSURE": "FIRED", "VOUCH": "FIRED"},
        lone_keeper=None,
    ),
    # u1. Missing evidence AND an open objection AND a covering owner decision. Rule 1 first.
    DecisionCase(
        "u1_missing_beats_objection_and_cover",
        ("HOLD", "missing evidence: ['x']"),
        {"BYPASS": "FIRED"},
        missing_required=("x",),
        open_objections=("obj-1",),
        covered_by="od-1",
    ),
    # u2. An open objection AND a covering owner decision. Rule 2 comes before rule 3: HOLD.
    DecisionCase(
        "u2_objection_beats_cover",
        ("HOLD", "skeptic objection open"),
        {"BYPASS": "FIRED"},
        open_objections=("obj-1",),
        covered_by="od-1",
    ),
    # u3. Nothing fired, nothing unknown, lone keeper true. Rule 9: NO_ACTION.
    DecisionCase("u3_nothing_fired", ("NO_ACTION",), {}, lone_keeper=True),
)


# ---------------------------------------------------------------------------------- conflict
@dataclass(frozen=True)
class ConflictCase:
    name: str
    claims: tuple  # two dicts: id, source, at (int or None), exception_to (id or None)
    expected: dict  # status, winner, basis, links


def claim(id_, source, at, exception_to=None) -> dict:
    return {"id": id_, "source": source, "at": at, "exception_to": exception_to}


CONFLICT_CASES: tuple[ConflictCase, ...] = (
    # l. Two established-actor statements, same time (100). Authority is equal. There is no
    #    exception between them. Recency cannot separate them (equal times). Rule 4:
    #    UNRESOLVED, both ids, no winner.
    ConflictCase(
        "l_equal_authority_same_time",
        (claim("c1", "established_actor", 100), claim("c2", "established_actor", 100)),
        {
            "status": "UNRESOLVED",
            "winner": None,
            "basis": "equal authority, no way to order them",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # l2. Equal authority, and one claim has no time. Recency cannot be applied. A missing time
    #     is never defaulted. UNRESOLVED.
    ConflictCase(
        "l2_equal_authority_time_missing",
        (claim("c1", "established_actor", 100), claim("c2", "established_actor", None)),
        {
            "status": "UNRESOLVED",
            "winner": None,
            "basis": "equal authority, no way to order them",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # m. Equal authority, no exception. Times 100 and 200. Rule 3: the newer claim, c2, wins.
    #    c1 is kept and superseded, not deleted.
    ConflictCase(
        "m_newer_wins_between_equals",
        (claim("c1", "established_actor", 100), claim("c2", "established_actor", 200)),
        {
            "status": "RESOLVED",
            "winner": "c2",
            "basis": "recency",
            "links": (("c1", "CONTRADICTS", "c2"), ("c2", "SUPERSEDES", "c1")),
        },
    ),
    # m2. Same, with the claims given in the other order. The newer one still wins.
    ConflictCase(
        "m2_newer_wins_regardless_of_order",
        (claim("c1", "low_history_actor", 500), claim("c2", "low_history_actor", 100)),
        {
            "status": "RESOLVED",
            "winner": "c1",
            "basis": "recency",
            "links": (("c1", "CONTRADICTS", "c2"), ("c1", "SUPERSEDES", "c2")),
        },
    ),
    # n1. Owner decision (old, time 1) against a system record (new, time 999). Rule 1: owner
    #     decision outranks a system record, whatever the times. Winner c1, basis authority.
    ConflictCase(
        "n1_owner_beats_system_record",
        (claim("c1", "owner_decision", 1), claim("c2", "system_record", 999)),
        {
            "status": "RESOLVED",
            "winner": "c1",
            "basis": "authority",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # n2. The README example: a statement by an established actor (new) against the grant
    #     history, a system record (old). Rule 1: system record wins. Both are kept.
    ConflictCase(
        "n2_system_record_beats_established_statement",
        (claim("c1", "established_actor", 900), claim("c2", "system_record", 10)),
        {
            "status": "RESOLVED",
            "winner": "c2",
            "basis": "authority",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # n3. Established actor against a low-history actor: established wins.
    ConflictCase(
        "n3_established_beats_low_history",
        (claim("c1", "low_history_actor", 50), claim("c2", "established_actor", 50)),
        {
            "status": "RESOLVED",
            "winner": "c2",
            "basis": "authority",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # n4. Low-history actor against hearsay: the low-history actor's own statement wins.
    ConflictCase(
        "n4_low_history_beats_hearsay",
        (claim("c1", "hearsay", 50), claim("c2", "low_history_actor", 50)),
        {
            "status": "RESOLVED",
            "winner": "c2",
            "basis": "authority",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
    # o. Equal authority. c2 is an explicit exception to c1 (the general statement). Rule 2
    #    comes before recency, so even though the general statement c1 is NEWER (300 vs 100) the
    #    exception is not overridden by it. NARROWED: both stand, the exception narrows the
    #    general. Link: c2 QUALIFIES c1. No winner is picked.
    ConflictCase(
        "o_exception_narrows_general",
        (
            claim("c1", "established_actor", 300),
            claim("c2", "established_actor", 100, exception_to="c1"),
        ),
        {
            "status": "NARROWED",
            "winner": None,
            "basis": "specificity",
            "links": (("c1", "CONTRADICTS", "c2"), ("c2", "QUALIFIES", "c1")),
        },
    ),
    # p. The exception has LOWER authority than the general statement. Rule 1 (authority) comes
    #    before rule 2 (specificity), so authority decides: the system record c1 wins.
    ConflictCase(
        "p_authority_before_specificity",
        (
            claim("c1", "system_record", 100),
            claim("c2", "established_actor", 200, exception_to="c1"),
        ),
        {
            "status": "RESOLVED",
            "winner": "c1",
            "basis": "authority",
            "links": (("c1", "CONTRADICTS", "c2"),),
        },
    ),
)

# Inputs resolve() must refuse rather than guess about.
BAD_CONFLICT_INPUTS: tuple[tuple[str, tuple], ...] = (
    ("one_claim", (claim("c1", "system_record", 1),)),
    (
        "three_claims",
        (
            claim("c1", "system_record", 1),
            claim("c2", "system_record", 2),
            claim("c3", "system_record", 3),
        ),
    ),
    ("unknown_source", (claim("c1", "rumour", 1), claim("c2", "system_record", 2))),
    ("same_id_twice", (claim("c1", "system_record", 1), claim("c1", "system_record", 2))),
)
