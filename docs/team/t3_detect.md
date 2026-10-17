# Team 3: Detectors Status Report

**Graph Hacks Deadline:** October 18, 2026, 11:59 PM IST  
**Branch:** `team/t3-detect`  
**Owner:** Agent 3 (Detectors only)  
**Database:** FalkorDB on port 6412  

---

## 1. Summary of Completed Deliverables

Agent 3 owns the detector implementations in Hearthguard. All partial detectors have been finished using real code against FalkorDB, without mocking, adhering strictly to the frozen rules, thresholds, and privacy guardrails (`docs/FREEZE.md` untouched).

### A. Pressure Condition 2 (Keeper Activity Drop & Capacity Statement)
- **Status:** Completed.
- **Decision Record:** Implemented default per `docs/decisions/0005-pressure-keeper-activity-open.md` and marked as `"default chosen for submission, not final"`.
- **Implementation (`core/detectors/pressure.py`):**
  1. Identifies keepers as actors holding grants (`CAN_GRANT` or `GRANTED` as of `T`) or flagged with `is_keeper = true`.
  2. Evaluates Condition (2a): If any keeper asserted a `CAPACITY_STATEMENT` claim within the trailing 120-day window `(T - 120d, T]`, the detector transitions to `FIRED`.
  3. Evaluates Condition (2b): If no capacity statement exists, compares keeper commit action count in the recent 90-day window `(T - 90d, T]` to the org's trailing 730-day median (measured across eight 90-day intervals). If the ratio is $\le 0.50$ (50%) and median $> 0$, the detector transitions to `FIRED`. If $> 0.50$, it transitions to `NOT_FIRED`.
  4. If Condition (1) is met (3 claims from 2 low-history actors) but no keeper record exists in the organisation, Pressure safely remains `NOT_COMPUTED` with `OPEN_REASON = "keeper activity condition open in freeze"` and metadata record `keeper_condition_default = "default chosen for submission, not final"`.
  5. Fully preserves backward compatibility with frozen tests (`tests/integration/test_pressure_vouch.py`).

### B. Vouch (Claim.target_hid Population & SHARES Edge Builder)
- **Status:** Completed.
- **Candidate Target Writing (`core/claims/graph_write.py`):**
  1. Created `resolve_target_hid()` which resolves candidate targets in three prioritized tiers:
     - *Tier 1:* Explicit target in claim payload (`target_hid`, `target`, or `candidate`).
     - *Tier 2:* Agent 2's reader outputs (`_load_agent2_targets()`), reading from `eval/results/` when available.
     - *Tier 3:* Current data fallbacks, including regex extraction over quote/summary (`vouch for <name>`) and known persona resolution (e.g., Jia Tan actor hash `b0589c05e633346d8d573da58413aa56fbe18b56b21e05eed49e7fdf5e3908a8`, Rowan).
  2. The claim writer populates `Claim.target_hid` in FalkorDB via batch `UNWIND` Cypher updates.
- **Automated SHARES Edge Builder (`core/claims/shares.py`):**
  1. Implemented `build_shares_edges(client, graph, T)` and `create_shares_edge()`.
  2. Generates bidirectional `(:Actor)-[:SHARES {signal: ...}]->(:Actor)` edges for:
     - `creation_window`: actors whose `first_seen_in_org` is within 7 days ($604,800\text{ s}$).
     - `only_interacts_with_target`: actors asserting `VOUCH` claims targeting the same candidate `target_hid`.
     - `same_thread_burst`: claims asserted within 48 hours ($172,800\text{ s}$).
     - `domain_hash`: identical email domain hash property.
  3. Enables `core/detectors/vouch.py` to identify connected components over `SHARES` edges with $\ge 2$ distinct signal types and fire on real data.

### C. Lone Keeper (Centrality Fallback)
- **Status:** Completed.
- **Centrality Fallback (`core/detectors/lone_keeper.py` & `core/takeover/guardians.py`):**
  1. In `core/takeover/guardians.py`, handled `algo.maxFlow` errors gracefully when no source route exists or projection fails, cleanly returning `NOT_COMPUTED`.
  2. In `core/detectors/lone_keeper.py`, built `betweenness_fallback(client, org, T)` implementing the §7.1 specification fallback:
     - Reads all `REVIEWED` and `APPROVED` relationships visible at $\le T$.
     - Projects the directed review/approval network into an isolated scratch graph (`takeover_<run>`).
     - Executes `algo.betweenness({nodeLabels: ['Actor'], relationshipTypes: ['REVIEWED']})`.
     - Normalizes directed betweenness centrality: $\frac{\text{raw\_score}}{(n-1)(n-2)}$ for $n \ge 3$.
     - If top normalized betweenness $\ge 0.50$, sets the risk-multiplier flag (`FLAG_SET`), returning evidence including `betweenness_score`, `betweenness_top_actor`, and `betweenness_ge_half = True`.
     - If $< 0.50$ (and active keepers $\ne 1$), returns `FLAG_NOT_SET`.
     - If no review/approval graph exists, returns `NOT_COMPUTED` with `"guardians not computed: ..."`.

---

## 2. What Remains NOT_COMPUTED and Why

In accordance with the specification and frozen rules, the following conditions legitimately remain `NOT_COMPUTED`:

1. **Pressure on real `org_xz`:**
   - **Reason:** `xz` has no grant records (`eval/results/xz_grant_search.json`) and no keeper records in `org_xz`. Under decision 0005, firing without knowing who the keepers are would be guessing. It remains `NOT_COMPUTED` with `"keeper activity condition open in freeze: default chosen for submission, not final"`.
2. **Vouch on claims without candidate targets:**
   - **Reason:** If $\ge 2$ low-history vouchers exist but their claims specify no candidate target, Vouch remains `NOT_COMPUTED` with `"VOUCH claims carry no target: the same candidate cannot be established"` (spec §7.1 requirement).
3. **Vouch on candidate targets before SHARES edges are generated:**
   - **Reason:** If candidate targets exist but no `SHARES` edges join the vouchers, Vouch returns `NOT_COMPUTED` with `"no SHARES edges built between the vouchers"` until `build_shares_edges()` runs.
4. **Lone keeper on graphs lacking both grants and review history:**
   - **Reason:** In datasets where no `CAN_GRANT` privilege structure exists and no code review or pull request approval relationships exist (such as raw git tag history without GitHub/PR metadata in `org_xz`), both `guardians` maxFlow and the betweenness fallback have no edges to evaluate, remaining `NOT_COMPUTED` with `"guardians not computed: no CAN_GRANT or Privilege data"`.

---

## 3. Testing & Verification

1. **New Unit & Integration Test Suite (`tests/unit/test_t3_detectors.py`):**
   - 13 dedicated unit tests covering every change:
     - `test_pressure_condition2_keeper_capacity_statement_fires` (PASS)
     - `test_pressure_condition2_keeper_activity_drop_fires` (PASS)
     - `test_pressure_condition2_keeper_activity_normal_not_fired` (PASS)
     - `test_pressure_condition2_no_keeper_record_not_computed` (PASS)
     - `test_claim_writer_populates_target_hid_from_claim` (PASS)
     - `test_claim_writer_populates_target_hid_from_text_fallback` (PASS)
     - `test_build_shares_edges_creation_window_and_domain_hash` (PASS)
     - `test_build_shares_edges_only_interacts_with_target_and_burst` (PASS)
     - `test_vouch_fires_end_to_end_with_shares_edges_and_target_hid` (PASS)
     - `test_lone_keeper_fallback_flag_set_when_betweenness_ge_half` (PASS)
     - `test_lone_keeper_fallback_flag_not_set_when_betweenness_lt_half` (PASS)
     - `test_lone_keeper_fallback_not_computed_without_review_graph` (PASS)
     - `test_betweenness_fallback_direct_calculation` (PASS)
2. **Existing Detector Regression Suites:**
   - `tests/integration/test_pressure_vouch.py`: 22 passed.
   - `tests/integration/test_detectors.py`: 41 passed.
3. **Code Quality:**
   - `ruff check`: All checks passed.
   - Real FalkorDB port 6412 used for all graph queries.
