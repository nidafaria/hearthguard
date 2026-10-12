# AI use log

Oct 12: Claude Code drafted pre-event notes (FREEZE.md, sources.yaml) from HEARTHGUARD.md.
Day 1: Claude Code bootstrapped the repo skeleton, Docker config, tooling, and CLAUDE.md.
Day 1: Claude Code wrote the FalkorDB client wrapper and the smoke test that re-checks every procedure the product depends on on the pinned 6.0.2 image.
Day 1: Claude Code wrote the core graph schema (constraints, range indexes), the as-of-T helper, the read-only guard and identifier hashing, with integration tests against the real container.
Day 1: Claude Code checked both public xz git sources, cached a bare mirror in data/raw, and recorded the URL, HEAD SHA and fetch time.
Day 1: Claude Code wrote the git parser (hashed authors, public persona only), the org_xz graph mapping, and an idempotent ingest that writes no grant edges.
Day 1: Claude Code wrote the as-of normal metrics (cadence, active keepers, release channel) and the quarter-end export to eval/results/xz_normal.json.
Day 1: Claude Code wrote the integration tests for idempotent ingest, no emails in the graph, and as-of correctness, including an independent Python recomputation of every metric.
Day 1: Claude Code wrote the PROPOSED OUTSIDER-edge decision record (status PROPOSED) and listed the cadence and active-keepers decisions as OPEN.
Day 1: Claude Code wrote takeover cost (SPpaths on a scratch graph) and guardians (the exact spec projection and maxFlow), both provisional.
Day 1: Claude Code wrote the hand-built fixtures with hand-derived answers, the tests, and the xz NOT COMPUTED status file.
