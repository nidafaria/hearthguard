# VERIFIED.md: Day 1 results

Day 1 (Oct 15) fills this table. Each row is one claim from the spec, checked against the running system or the live source. Nothing is marked verified before then.

| Item | Spec claim | Check | Result | Date | Status |
|---|---|---|---|---|---|
| FalkorDB image pin | `falkordb/falkordb:6.0.2` (newest 6.0.x tag on Docker Hub, pushed 2026-10-08) | `docker compose up -d`; `redis-cli PING`; `MODULE LIST`; `CONFIG GET dir` | PONG; module ver 60002; data dir `/var/lib/falkordb/data`; volume mounted there | 2026-10-12 | pinned at bootstrap |
| algo.SPpaths | `algo.SPpaths({sourceNode, targetNode, relTypes, weightProp})` | `test_sppaths_yields_path_and_weight`; yields `path`, `pathWeight`; a→c shortest weight 3 (not direct 5) | pass | 2026-10-12 | pass |
| algo.maxFlow | `algo.maxFlow({sourceNodes, targetNodes, capacityProperty, relationshipTypes})`; yield `maxFlow`. Two types raises `'relationshipTypes' is required and must contain exactly one type` | `test_maxflow_rejects_two_relationship_types`; `test_guardians_one_middle_person_is_1` (OUTSIDER→k1→PRIV) = 1; `test_guardians_two_parallel_people_is_2` = 2. Spec §7.4 projection run as written | pass | 2026-10-12 | pass |
| algo.WCC | `algo.WCC({nodeLabels, relationshipTypes})`; yields `node`, `componentId` | `test_wcc_components_on_two_clusters`: two clusters get distinct ids, members share one | pass | 2026-10-12 | pass |
| algo.labelPropagation | `algo.labelPropagation({nodeLabels, relationshipTypes})`; yields `node`, `communityId` | `test_label_propagation_separates_two_cliques`: each triangle one label, no shared label (observed A=[0], B=[3]) | pass | 2026-10-12 | pass |
| algo.betweenness | `algo.betweenness({nodeLabels, relationshipTypes})`; yields `node`, `score` | `test_betweenness_star_hub`: hand value 12 for hub (4×3 ordered leaf pairs, edges both ways); leaves 0. Score counts ordered pairs, unnormalised | pass | 2026-10-12 | pass |
| GRAPH.COPY | `GRAPH.COPY src dst`; fails if dst exists | `test_graph_copy_is_independent`: after a write to the copy, src=3 nodes, dst=4. Second copy into an existing key errors `destination key already exists` | pass | 2026-10-12 | pass |
| algo.CCH | Not available in 6.0 (§5.1): must not be used | `test_cch_is_unavailable`: error `Unknown function 'algo.CCH'` | pass (confirmed unavailable) | 2026-10-12 | pass |
| Per-query timeout | Spec §5.1: `TIMEOUT` config ambiguous; set explicit per-query timeouts | `test_query_timeout_is_enforced`: `timeout` argument in ms; 30000×30000 cross join with 50 ms limit fails `Query timed out` after 47 ms | pass | 2026-10-12 | pass |
