# FREEZE.md: Hearthguard frozen rules

Status: DRAFT, local only. NOT FROZEN YET.
Written: 2026-10-12. Freeze must happen before Oct 15, 12:01 AM IST.
Source spec: docs/HEARTHGUARD.md §7, §10.1, §10.2, §11.2, §15, §18.
Public gist: none (local-only project)
SHA-256 of this file: stored in docs/FREEZE.sha256 (a file cannot contain its own hash).

Rule: nothing in this file changes after the freeze. Any change needs a new dated
file and a note in docs/decisions/. Both results are reported if anything changes.

Label key:
- Text with no label is copied from the spec.
- **PROPOSED** means the spec does not state this value. It is our choice. Review it before freezing.
- **NOT FROZEN** means the section cannot be frozen yet.

---

## 1. Four moves and Lone keeper (spec §7.1)

Every detector is evaluated as of time T. It reads only events with at <= T.

| Move | Fires when (as of T) | LLM? |
|---|---|---|
| Pressure | In the last 120 days: at least 3 PRESSURE or URGENCY claims from at least 2 distinct actors. Those actors have < 90 days of history in this org, or < 5 actions. AND keeper activity in the last 90 days is <= 50% of this org's own trailing two-year median, OR a keeper CAPACITY_STATEMENT exists in the window. | Yes (Reader) |
| Vouch | At least 2 low-history actors VOUCH for the same candidate. Those actors sit in the same WCC / labelPropagation component over SHARES edges that carry at least 2 distinct signal types. | Yes (Reader) |
| Rush | An actor gets a sensitive privilege with days-since-first-action below this org's own 10th percentile for that privilege. If the org has fewer than 5 historical grants, the rule is < 180 days. | No |
| Bypass | A sensitive action's Path differs from the remembered normal on at least 1 pack-defined property. OSS: CI -> none, provenance -> none, new key, publisher outside the set, release artifact differs from tagged source. Finance: portal -> email, no callback, fewer approvers than usual. | No |
| Lone keeper (multiplier only, never fires alone) | Guardians = 1, OR active_keepers = 1. Fallback if algo.maxFlow fails on Day 1: betweenness >= 0.5 on the approval/review graph. | No |

Pressure and Vouch go to HOLD("reader unavailable") if the LLM is down.
Rush, Bypass, Lone keeper, takeover cost and visibility gaps keep running.

The Pressure query (spec §7.6) is corrected in Spec fix d.

---

## 2. Conflict policy for contradictory claims (spec §7.2)

Claims are kept as written. Contradictions are linked, not removed.

1. Authority: owner decision > system record (grants, release metadata, ERP log) > statement by an established actor > statement by a low-history actor > hearsay (reported).
2. Specificity: an explicit exception narrows a general statement.
3. Recency: between equals, the newer claim wins.
4. UNRESOLVED: equal authority and still in conflict -> the Liaison asks the person in charge.

---

## 3. Decision policy (spec §7.3)

```python
def decide(e):
    if e.missing_required:                 return HOLD(f"missing evidence: {e.missing_required}")
    if e.open_objections:                  return HOLD("skeptic objection open")
    if e.covered_by_owner_decision:        return SUPPRESS(e.owner_decision_ref)
    moves = e.fired                        # subset of {PRESSURE, VOUCH, RUSH, BYPASS}
    risk  = 1.5 if e.lone_keeper else 1.0  # lone_keeper := guardians == 1 or active_keepers == 1
    if "BYPASS" in moves:                  return NOTE(pattern="path-bypass", urgency="high")
    if len(moves) >= 2 and risk * len(moves) >= 3.0:
                                           return NOTE(pattern="takeover-moves", urgency="high")
    if len(moves) >= 2:                    return NOTE(pattern="takeover-moves", urgency="medium")
    if len(moves) == 1 and e.lone_keeper:  return WATCH(moves=moves, explain=True)
    return NO_ACTION(explain=e.breakdown)
```

Who can trigger a note (fix e):
- Bypass alone can send a note.
- Any other note needs at least 2 fired moves (spec §18).
- One non-Bypass move never sends a note. With Lone keeper it only sets WATCH.

Every note is a question about the situation. It never says a person is an attacker.

---

## 4. Takeover cost and Guardians (spec §7.4)

**Takeover cost (as of T):** the minimum total approvals_required along any path from a synthetic OUTSIDER node to the sensitive privilege.
- Edges used: CAN_GRANT and GRANTED (both in spec §6.1).
- Edge TRUSTS: **PROPOSED**, not in §6.1. See Spec fix a. Not used until added to §6.1.
- Computed with algo.SPpaths, weightProp = 'approvals'.

**Guardians (as of T):** the minimum vertex cut between OUTSIDER and the privilege.
- Computed with algo.maxFlow on a node-split projection. Each person is split in -> out with capacity 1. All other edges have capacity 1000000. All edges use one relationship type, CAP.

```cypher
// Projection (built in the same org graph or a scratch copy) — VERIFY DAY 1
MATCH (k:Actor)-[:CAN_GRANT]->(p:Privilege {kind:$privilege})
MERGE (ki:Flow {id: k.hid + ':in'})  MERGE (ko:Flow {id: k.hid + ':out'})
MERGE (ki)-[:CAP {c: 1}]->(ko)
MERGE (src:Flow {id:'OUTSIDER'})     MERGE (dst:Flow {id:'PRIV:' + $privilege})
MERGE (src)-[:CAP {c: 1000000}]->(ki)
MERGE (ko)-[:CAP {c: 1000000}]->(dst);

// Guardians
MATCH (s:Flow {id:'OUTSIDER'}), (t:Flow {id:'PRIV:' + $privilege})
CALL algo.maxFlow({sourceNodes:[s], targetNodes:[t], capacityProperty:'c', relationshipTypes:['CAP']})
YIELD maxFlow
RETURN maxFlow AS guardians
```

Takeover cost and Guardians are organisation-level structure. They may be shown on records the user does not own, and in the census. They are never attached to a person.

Open: the spec does not say which edges connect OUTSIDER to actors. **PROPOSED** to define before Day 1. See Open items.

---

## 5. Visibility gaps (spec §7.5)

Gaps are computed by query. They are never hand-labelled.
- UNREACHABLE: the signal sat in a place the decision-maker's role did not watch before the signal time.
- UNNOTICED: the role watched that place, but the decision never referenced the signal.

**Runs on:** `ecosystem_<id>` (spec §6.2). It uses only ecosystem labels (Decision, Identity, Signal, Place, Role). It does not need org data. See Spec fix c.

```cypher
// For a decision, which earlier signals about the same identity were recorded in places
// the decision-maker's role did not watch (UNREACHABLE) or watched but never referenced (UNNOTICED)?
MATCH (d:Decision {ref:$decision})-[:MADE_IN]->(dp:Place)<-[:WATCHES]-(r:Role)
MATCH (d)-[:CONCERNS]->(i:Identity)-[:SAME_AS*0..2]-(j:Identity)
MATCH (j)-[:EMITTED]->(s:Signal)-[:RECORDED_IN]->(sp:Place)
WHERE s.at < d.at
OPTIONAL MATCH (r)-[w:WATCHES]->(sp) WHERE w.since < s.at
OPTIONAL MATCH (d)-[ref:REFERENCES]->(s)
RETURN s.kind, s.ref, sp.ref AS seen_in,
       CASE WHEN w IS NULL THEN 'UNREACHABLE'
            WHEN ref IS NULL THEN 'UNNOTICED' END AS gap
```

Edges CONCERNS, EMITTED and REFERENCES are not in spec §6.2. **PROPOSED** to add them to §6.2 before the freeze.

---

## 6. False-alarm study population (spec §10.2)

Stated in spec: about 30 real projects that legitimately added maintainers, 2021–2025, plus clean red-team copies.

Selection rule: **PROPOSED** (the spec does not state these rules)
- Source: the public git history of each candidate repo, read through the GitHub API.
- Include: a repo where a maintainer or CODEOWNERS entry was added between 2021-01-01 and 2025-12-31.
- Exclude: archived repos, repos with fewer than 2 years of history, and any repo used in the xz, event-stream or axios cases.
- Order: sort by full repo name (A to Z). Take the first 30 that pass the rules.
- The list is written to data/sources.yaml with the fetch date before any detector runs on it.

Status: **PROPOSED**. Not frozen until the list is written and dated.

---

## 7. Census population (spec §11.2)

**NOT FROZEN.** Source name and URL are unknown.

- Target: N >= 100. The spec gives N = 100 as the census command (§10.2: `make census N=100`) and N >= 100 as the Should target (§15). §11.2 does not fix N. **PROPOSED.**
- Source: a public list of npm packages ranked by downloads. Name and URL: **TBD, VERIFY Day 1**. Record the fetch date.
- Include: the top N entries that have a linked public GitHub repo. **PROPOSED.**
- Exclude: packages with no public repo. **PROPOSED.**
- Output rule (stated in spec §11.2 and §4.5 rule 5): aggregates only. No per-package output, ever.

The census cannot be frozen until the source name and URL are filled and the fetch date is recorded.

---

## 8. Thresholds (spec §7 and §10.1)

- The thresholds in §1 are the frozen defaults. They are published with a date before Oct 15.
- Rule: the thresholds must not be tuned against xz, event-stream, axios, the finance case, the census, or any red-team data.
- Packs supply vocabulary and path definitions only, never thresholds.
- Rule: no threshold changes after the first evaluation run. Any post-hoc change is logged, and both results are reported (spec §10.1 item 4).
- Every detector is evaluated as of time T, using only events with at <= T.

---

## Open items (not fixed here; decide before the freeze)

- **OUTSIDER edges are not defined.** The spec does not say which edges connect the synthetic OUTSIDER node to actors. Takeover cost and Guardians cannot be computed without them. **PROPOSED:** define before Day 1.
- **Pressure query omits keeper activity.** The §7.6 query does not include the keeper-activity condition from §7.1 (ratio <= 50% of trailing two-year median, or CAPACITY_STATEMENT). Update the query before the freeze.
- **Bypass query is partial.** The §7.6 query checks channel, verified and approvers. §7.1 also lists CI, provenance, new key and publisher for OSS. The query also reads Normal with action_kind, which §6.1 does not store.
- **Census source** (Spec fix f) and the **false-alarm list** (§6) are not yet filled in.
- **Hash:** this file's hash is recorded in docs/FREEZE.sha256 after writing. It must be re-recorded if this file changes.

---

## Spec fixes

These fixes change the spec's text where it was not consistent with itself. Each one is listed so a judge can check it.

**a. TRUSTS is not in the model.** Spec §7.4 uses the edge TRUSTS. Spec §6.1 has no TRUSTS edge.
- Fix: the frozen text uses CAN_GRANT and GRANTED from §6.1.
- TRUSTS is marked **PROPOSED**: an edge from a keeper to any actor the keeper has granted a privilege to, where that actor has < 90 days of history. Not used until it is added to §6.1.

**b. Trust-path query uses names not in the model.** Spec §7.6 (trust path) uses VOUCHED_FOR, REVIEWED and GRANTED. Only GRANTED is in §6.1.
- Fix: relTypes becomes ['CAN_GRANT', 'GRANTED'], both from §6.1.
- Fix: weightProp changes from 'w' to 'approvals', to match §7.4. 'w' is not in the model.
- VOUCHED_FOR and REVIEWED are removed. The vouch relationship is covered by SHARES edges and VOUCH claims (§7.1). Those are not actor-to-privilege edges, so they do not belong on this path.
- Corrected query:
```cypher
MATCH (a:Actor {hid:$hid}), (p:Privilege {kind:$privilege})
CALL algo.SPpaths({sourceNode:a, targetNode:p, relTypes:['CAN_GRANT','GRANTED'], weightProp:'approvals'})
YIELD path, pathWeight
RETURN path, pathWeight
```

**c. Visibility-gap query names the graph.** Spec §7.5 uses Identity, Signal and Decision, which are ecosystem labels (§6.2). It does not use org labels.
- Fix: the query runs on `ecosystem_<id>`. This is now stated in §5 above.
- The edges CONCERNS, EMITTED and REFERENCES are not in §6.2. **PROPOSED** to add them to §6.2.

**d. Pressure query uses a value that is not stored.** Spec §7.6 (Pressure) uses a.actions_at_T. §6.1 does not store that value.
- Fix: it is computed in the query as the count of DID edges with at <= T. a.first_seen_in_org is stored (§6.1), so it stays as written.
- Corrected query:
```cypher
MATCH (a:Actor)-[:ASSERTED]->(c:Claim)
WHERE c.kind IN ['PRESSURE','URGENCY'] AND c.at > $T - $d120 AND c.at <= $T
OPTIONAL MATCH (a)-[:DID]->(x:Action) WHERE x.at <= $T
WITH a, c, count(x) AS actions_at_T
WHERE a.first_seen_in_org > $T - $d90 OR actions_at_T < 5
WITH collect(DISTINCT a.hid) AS actors, count(c) AS claims, collect(c.id) AS evidence
WHERE size(actors) >= 2 AND claims >= 3
RETURN actors, claims, evidence
```
- This query does not yet include the keeper-activity condition from §7.1. See Open items.

**e. Who can send a note.** Spec §7.3 code lets Bypass alone send a note. Spec §18 says the policy needs at least 2 moves except Bypass. These agree, but the spec did not say so in words.
- Fix: the frozen text states both rules. Bypass alone can send a note. Any other note needs at least 2 fired moves. This is in §3 above.

**f. Census source is unknown.** Spec §11.2 says "VERIFY the list source on Day 1" and gives no name or URL.
- Fix: the source is marked "TBD, VERIFY Day 1". The census section is marked **NOT FROZEN** until it is filled. This is in §7 above.

---
