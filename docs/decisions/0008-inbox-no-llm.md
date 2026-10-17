# 0008: The inbox answers thread questions without an LLM

**Status: OPEN.** Chosen by the build agent for block A, not decided by the owner. The owner should confirm or reverse it.

## Context

Spec 8.1 and 12.2 let the Investigator use an LLM planner for thread questions. The Groq daily allowance for this project is used up (GROQ_API_KEY is in .env, but the quota is spent), so an LLM answer cannot be produced or tested today.

## Decision

Thread questions are answered by a fixed router over tested tools only (core/agents/investigator.py): takeover cost, guardians, remembered normal, review counts, and a has-this-happened-before summary from saved results. No model is called. Each answer records `llm_calls: 0`.

Questions that ask for a judgement about a person, or ask the system to approve, block, revoke or ignore its rules, are refused with the facts. Text inside a question is stored as text and changes nothing.

## Consequences

- Questions outside the router get "no tested tool covers that", not a guess.
- The spec's wording requirement ("refuses to judge people") is met by the fixed refusal sentence, not by model behaviour.
- When an LLM is available again, the router can be replaced for free-text planning; the refusal and tool-only evidence rules stay as they are (spec 8.1: only tool outputs count as evidence).

## Open questions for the owner

1. Accept the no-LLM router for the demo, or wait for an LLM planner?
2. Should the list of answerable questions be widened, and by whom?

## Default chosen for submission, not final (2026-10-18)

- Accept the no-LLM router for the demo; the list of answerable questions is not widened. Why: it is tested, makes zero model calls, and refuses to judge people.
