# 0001: OUTSIDER edges, takeover cost and guardians

**Status: PROPOSED.** This is a proposal. The spec does not define it. It stays open until the owner decides. Every value computed under it is provisional.

Related: docs/HEARTHGUARD.md §2.2, §6.1, §7.4, §8.5. docs/FREEZE.md "Open items" (OUTSIDER edges). Nothing here edits the freeze files.

## The rule (PROPOSED)

- A synthetic `(:Flow {id:'OUTSIDER'})` node is connected to every `(:Actor)` with an edge `OUTSIDER_ENTRY {approvals: 1}`.
- **Takeover cost** for privilege P = the minimum sum of `approvals` along a path from OUTSIDER to P over `CAN_GRANT` and `GRANTED` edges (spec §7.4), found with `algo.SPpaths` and `weightProp: 'approvals'`.
- **Guardians** = the minimum vertex cut between OUTSIDER and P, from the exact §7.4 projection and `algo.maxFlow`.
- Both are organisation-level structure (§4.5 rule 4). Neither is ever stored on an Actor.

## How this implementation reads the rule, and why

The proposal as literally written has a conflict. If the entry edge carries `approvals: 1` and `SPpaths` adds every edge on the path, a lone keeper whose `CAN_GRANT` needs 1 approval costs 1 + 1 = 2, and a two-approval grant costs 1 + 2 = 3. But spec §2.2 says a lone keeper has takeover cost **1**, and §8.5 says the two-keeper rule (`approvals_required = 2`) makes it **2**.

This implementation keeps the entry edge at `approvals: 1`, as proposed, because `SPpaths` needs a weight on every edge it walks. It then takes the cost as the sum over the `CAN_GRANT` and `GRANTED` edges only, as the rule's own sentence says, by subtracting the entry hop:

`cost = pathWeight - 1`

Every path starts with exactly one entry edge from OUTSIDER, so this does not change which path is cheapest. **Decision for the owner:** keep this reading, or set the entry weight to 0 and drop the subtraction. The numbers are the same.

## Defaults this implementation had to choose (all PROPOSED)

| Item | Choice | Why |
|---|---|---|
| Weight property | Org graphs store `approvals_required` on `CAN_GRANT` (spec §6.1). The scratch graph copies it into `approvals`, the name `SPpaths` is called with (spec §7.4). | The spec names the two differently. |
| Missing count | A `CAN_GRANT` or `GRANTED` edge with no count counts as 1 approval. | One human is one approval. `SPpaths` itself treats a missing weight as 1. |
| `GRANTED` | Counts 1 approval (a holder is one human to win). | §6.1 gives `GRANTED` no count. |
| Time | An edge with `at` is used only if `at <= T`. An edge with no `at` is always used. | §6.1 gives `CAN_GRANT` no `at`. Real data should stamp `at`, or a past T could see a grant created later. |
| Which actors get an entry edge | Only actors with a grant edge to P at `<= T`. | An actor with no such edge cannot lie on a route to P, and an actor not yet in the org cannot hold a grant, so the cost and the cut are the same as with an edge to every actor. |
| Guardians edges | `CAN_GRANT` only, exactly as the §7.4 projection reads. `GRANTED` holders are not in the cut. | The projection text is exact. See the open question below. |
| Scratch graph | Both computations build `takeover_<run>` from as-of reads of the org graph and drop it afterwards, so the org graph never gets a Flow node. | The projection and `SPpaths` need OUTSIDER and the entry edges in the same graph as the actors. |
| No path | A real result: cost `None`, reason `no path`, guardians 0. | Spec §1: "no path found" is a real result. |
| No data | If the org has no `Privilege` node of that kind, the result is NOT COMPUTED, not "no path". | Without grant data, "no path" would be a false finding. |

## Open question this rule exposes

Cost counts a `GRANTED` holder as a route (cost 1), but the §7.4 guardians projection ignores `GRANTED` (cut 0). The two numbers can disagree for an organisation whose rights are recorded only as `GRANTED`. Decide whether the projection should also read `GRANTED`. It is left exactly as the spec has it until then.

## Pending decisions from Prompt 4

Both are about the remembered-normal metrics in `core/normal/metrics.py`. Neither is decided here.

1. **Cadence. Status: OPEN.** `commit_cadence_days` is the median gap between consecutive commits. On xz it is minutes (0.004 to 0.019 days) at every quarter-end, because commits arrive in bursts and the median sits inside a burst. Options: replace it with the median gap between distinct commit days, or between bursts, or keep it and add a second metric.
2. **Active keepers. Status: OPEN.** `active_keepers` counts distinct commit authors in the trailing 90 days. An author is not always someone with commit access, so it can overcount keepers. Options: count committers, or count maintainers once grants are known. This feeds the Lone keeper condition (§7.1), so it matters.
