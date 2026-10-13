# 0007. Learned exceptions: a deterministic filler, and a gate on the frozen decision code

Status: PROPOSED (block E). Owner: block E. Spec: docs/HEARTHGUARD.md 8.3, 9, 10.2, 12.2.

## Context

Spec 8.3 has the Liaison fill a strict exception template with an LLM, up to 3 attempts, then a
human writes it. The LLM allowance may be used up, and CLAUDE.md keeps the LLM out of the decision
path. The exception then has to be checked against the red-team suite and must lose no planted
campaign.

## Decision

1. **The filler is a fixed table, not an LLM** (`core/learning/filler.py`). A dismissal reason
   selects one row: words to a move and fixed clauses. The reason is never copied into the
   template. Up to 3 attempts (whole words, then word stems). No match after 3: Human review.
   The same reason always gives the same template.
2. **The template is three fields plus an id** (`core/learning/templates.py`): `applies_to` is one
   real move, `when` is up to two clauses from a fixed set of building blocks, `effect` is the one
   literal `exclude_actor_from_move`. `extra="forbid"`, so no takeover-cost or guardian field fits.
3. **Safety rules** (`core/learning/safety.py`), checked on every proposal: never Bypass; one move
   only; no field that could change takeover cost or guardians; a concrete condition that names a
   declared list.
4. **The gate calls the frozen code unchanged** (`core/learning/gate.py`, `decide_with_unknowns`).
   It replays the saved red-team suite (`eval/results/redteam_xz.json`, 200 campaigns) and the
   saved real-case rows (xz, tallowdate). The replay is a **worst case**: every firing of the
   proposed move is removed at every point. The saved suite does not record which actor fired a
   move, so an actor-level exception cannot be replayed exactly; the worst case is an upper bound
   on the loss. The gate refuses to pass if the baseline replay does not reproduce every saved
   decision.
5. **End states** (`core/learning/states.py`): Adopted (owner approval after a pass, or K = 3
   independent agreements), Shadow (passed the gate, records what it would suppress), Human review
   (no building block), Rejected (safety rule or lost detection; kept with its reason).

## What this gives, on the saved files

- Pressure: passes. Pressure never reaches FIRED in the saved suite (docs/decisions/0005), so
  removing it changes no planted decision. The pass is real but says little about Pressure.
- Vouch: rejected, 18 of 167 planted campaigns lost under the worst case.
- Rush: rejected, 22 of 167 lost under the worst case.

## Known limits

- No exception changes a live decision yet. Adopted does not act. Shadow only records.
- Real-case rows in the saved files are all HOLD with unknown moves, so the real-case check can
  lose nothing. It is not evidence of safety on real data.
- The worst-case bound may reject an exception that would be safe at the actor level. Rejection
  means "not proven safe under the bound", not "unsafe".
- Chaos seeds that draw the same pattern produce the same template, so the same exception id. The
  playbook holds no organisation data, so a seed-specific actor name cannot enter the template.

## Why

Spec 8.3 says "nothing untested ever acts" and "zero planted campaigns may be lost". A
deterministic filler and a gate on the frozen code meet both without a model call, and the result
can be re-run by anyone from the saved files.
