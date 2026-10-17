# 0004: Reader claims from the mailing list enter org_xz

**Status: OPEN.** This is our choice. The spec does not say how list posters who have no commits are represented. Every Pressure and Vouch result built on it is provisional.

## What was done

`core/claims/graph_write.py` writes the Reader's accepted claims into `org_xz` (spec §6.1, "Text understanding"): `Source`, `Span`, `Claim`, and `Actor-[:ASSERTED]->Claim`. MERGE on unique keys, so it can be rerun.

- A poster whose hashed email matches a git author maps to the **existing** Actor, which is left untouched.
- A poster with no commits gets a **new** Actor with `source = 'mail'` and `first_seen_in_org` set to the time of their first claim.

## Consequences to know

1. `org_xz` now has more Actor nodes than the 68 from git alone. Nothing else reads them: the normal metrics and takeover checks use `DID` edges, which mail-only actors do not have.
2. "Low history" is judged literally as the spec says: history < 90 days **or** fewer than 5 actions. A mail-only actor has 0 actions, so is always low-history, even if they posted for years before 2021 (we only hold 2021 to 2024). **This makes the low-history filter in Pressure and Vouch weaker than intended for list posters.** Options: count list messages as actions; or only treat an actor as low-history if their first message in the cache is also their first ever (we cannot know that).
3. The Reader does not extract a candidate, so `Claim.target_hid` is empty. Vouch cannot establish "the same candidate" and returns NOT_COMPUTED when it reaches that step.
4. No SHARES edge is built. `creation_window` needs account creation dates, which are not in the public record we hold; `domain_hash` over mail domains would mostly match public providers. Without SHARES edges Vouch cannot fire.

## Not decided here

Whether to count mail messages as actions, and whether GitHub account data may enter the graph. Both change results, so the choice stays with the owner.

## Default chosen for submission, not final (2026-10-18)

- Mail messages do not count as actions, and GitHub account data does not enter the graph. Why: the literal spec reading of low-history is kept, the graph keeps only public git and list data already held, and no result changes. The weaker low-history filter for list posters stays a stated limit; Vouch stays NOT COMPUTED.
