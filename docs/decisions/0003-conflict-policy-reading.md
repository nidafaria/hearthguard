# 0003: How the conflict policy (spec §7.2) is read in code

**Status: PROPOSED.** The conflict policy itself is FROZEN and is implemented as written in `core/policy/conflict.py`. These are the choices the spec leaves open. They stay open until the owner decides.

## Taken as written

Authority (owner decision > system record > established actor > low-history actor > hearsay), then specificity (an explicit exception narrows a general statement), then recency (the newer claim wins between equals), then UNRESOLVED. Both claims are always kept; the result links them with the claim relations in spec §6.1: CONTRADICTS always, plus SUPERSEDES for a recency win or QUALIFIES for a narrowing.

## Reading choices

1. **Where UNRESOLVED comes from.** Applied in the spec's order, recency separates every equal-authority pair that has two different times. So UNRESOLVED arises only when the times are equal or one is missing. A missing time is never defaulted, so it is UNRESOLVED. **Question for the owner:** is that what rule 4 means? If UNRESOLVED should also cover two *different* actors of equal authority who disagree, with recency applying only to one actor correcting themselves, that is a one-line change plus one new field on the claim (who said it).
2. **The caller supplies the authority class** (`owner_decision`, `system_record`, `established_actor`, `low_history_actor`, `hearsay`). `resolve()` does not look at the graph. Deciding whether an actor is low-history (spec §7.1: under 90 days or under 5 actions) or whether a claim is reported (`modality`) is a separate, later step.
3. **A specificity relation is explicit.** A claim names the general claim it narrows (`exception_to`). The code does not guess it from text. It applies only between claims of equal authority, because authority is checked first: a lower-authority exception does not narrow a higher-authority statement.
4. **NARROWED is not a winner.** When an exception narrows a general statement, both stand and no winner is named. The exception governs its narrow scope.
5. **Bad input is refused:** not exactly two claims, equal ids, an unknown authority class, a non-integer time, or two claims that are each an exception to the other.

## Default chosen for submission, not final (2026-10-18)

- Keep all five reading choices as built. Why: UNRESOLVED on equal-authority equal-or-missing time is the careful reading, since it never names a winner on thin evidence, and the code needs no change.
