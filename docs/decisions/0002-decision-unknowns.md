# 0002: Unknown inputs to the decision policy

**Status: PROPOSED.** This is an addition. The spec does not state it. It stays open until the owner decides. The frozen decision policy (spec §7.3) is not edited and not extended: everything here sits in a separate function, `decide_with_unknowns()` in `core/policy/decision.py`.

Related: docs/HEARTHGUARD.md §7.1 (reader unavailable), §7.3, §18. Fixtures: `tests/fixtures/decision_cases.py` (written and committed before the code).

## The problem

The frozen `decide(e)` reads `e.fired`, the set of moves that fired. A move whose detector returned NOT_COMPUTED is not in that set, so the policy sees it exactly as it sees a move that was checked and did not fire. On real xz that is the usual case: Rush, Bypass and Lone keeper are all NOT_COMPUTED. Without a guard the policy would answer NO_ACTION, which reads as "we looked and found nothing" when the truth is "we could not look".

## What is already in the spec's frame (not an addition)

A Pressure or Vouch that cannot run because the reader (LLM) is unavailable is passed to `decide()` as a **missing input**: `missing_required` gets `"PRESSURE: reader unavailable"`. Rule 1 of the frozen policy then returns `HOLD("missing evidence: [...]")`. This uses the spec's own first rule and the spec's own sentence ("Pressure and Vouch go to HOLD(reader unavailable)"). It is never turned into "not fired".

## The PROPOSED additions

| # | Rule | Why |
|---|---|---|
| 1 | **Unknown move.** A move whose detector is NOT_COMPUTED is recorded in `unknown_moves`. It is never counted as fired and never as not fired. If `decide()` returns **NO_ACTION** and any move is unknown, return `HOLD("move unknown: <names>")`, names in the order PRESSURE, VOUCH, RUSH, BYPASS. | "Nothing found" must not be reported when a move could not be checked. |
| 2 | **Unknown Lone keeper.** Lone keeper is a multiplier, not a move. When it is NOT_COMPUTED it is passed to `decide()` as `False` (the function needs a bool) and recorded as `lone_keeper_unknown`. If `decide()` returns **NO_ACTION**, exactly one move fired, and Lone keeper is unknown, return `HOLD("input unknown: LONE_KEEPER")`. | That is the one case where the multiplier decides between WATCH and NO_ACTION. With no move fired the multiplier cannot matter, so nothing is held. |

Rule 1 is the owner's request. Rule 2 is my extension of the same idea; the owner can drop it by deleting one `if` in `decide_with_unknowns()` and the three fixture cases r, s and t.

## What the layer does not do

- It changes **only** a NO_ACTION result. Every NOTE, WATCH, SUPPRESS and HOLD from `decide()` is returned exactly as it is. An unknown move therefore never weakens or removes a NOTE that other moves earned.
- It adds no branch to `decide()`. A test checks that `decide()` has exactly the spec's seven `if` statements and reads only the spec's fields, and a second test runs the spec's own code block against it on all 256 combinations of the gate inputs.
- It never fires a move. It only turns "no action" into "hold".

## Open questions for the owner

1. A NOTE can still be sent while a move is unknown (case n: Bypass unknown, Pressure and Vouch fired, so NOTE medium). Its urgency might have been higher had Bypass been known. The breakdown lists the unknown move, so the note can say so. Should an unknown move cap or annotate the urgency?
2. Lone keeper unknown with two moves fired (case t) gives `medium`, because unknown is passed as false. With Lone keeper true it would be `high`. The breakdown records `lone_keeper_unknown`. Should this be a HOLD instead?

## Default chosen for submission, not final (2026-10-18)

- Keep both proposed rules (unknown move and unknown Lone keeper turn NO_ACTION into HOLD). Why: HOLD is the careful answer when something could not be checked.
- Open question 1: an unknown move annotates a NOTE through the breakdown and does not cap urgency. Why: capping would invent a rule the spec does not state.
- Open question 2: Lone keeper unknown with two moves fired stays `medium` with `lone_keeper_unknown` recorded. Why: changing it to HOLD would change a fixture expectation; the breakdown already shows the gap.
