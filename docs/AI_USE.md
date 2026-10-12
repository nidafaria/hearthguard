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
Day 2: Claude Code wrote the Rush detector (leave-one-out 10th percentile, 180-day fallback, never defaults a missing timestamp) with the formula in the code comment.
Day 2: Claude Code wrote the Bypass detector (per-property remembered normal; absent or tied values are NOT_COMPUTED, never a match) and the Lone keeper multiplier flag on top of guardians.
Day 2: Claude Code wrote the hand-derived detector fixtures, the tests, and the xz NOT_COMPUTED status file with no values.
Day 2: Claude Code wrote the decision and conflict policy fixtures with hand-derived results and committed them before any implementation.
Day 2: Claude Code implemented the frozen decision policy line for line, the conflict policy, and the separate PROPOSED unknown-input layer, with unit tests including an oracle run of the spec code.
Day 2: Claude Code fixed Bypass so a shared Path node gives NOT_COMPUTED, found and worked around a FalkorDB 6.0.2 crash on aggregates with NULL columns, and recorded the xz status diff.
Day 2: Claude Code built a resumable, rate-limit-aware fetch-and-cache layer with a sidecar (URL and fetch time) for every response, tested against a local HTTP server.
Day 2: Claude Code cached 300 xz-devel messages (2021 to 2024 plus msg00512 to msg00571) with hashed authors, and started the GitHub pull request, review, comment and file-history cache (partial: no token, rate limited).
Day 2: Claude Code wrote the raw-cache inventory (counts and dates only) and recorded the findings, including that the archive shows no author email and that MAINTAINERS and CODEOWNERS have no GitHub history.
Day 2: Claude Code finished the GitHub cache with the token (383 requests, 436 responses, complete) and confirmed the token appears in no file or log.
Day 2: Claude Code noticed the hash salt changed and recorded that the existing org_xz graph no longer matches it.
Day 2: Claude Code dropped org_xz and rebuilt it with the rotated salt (ingest, normal, takeover and detector status), confirming 68 actors and that every graph id matches the current salt.
Day 2: Claude Code wrote the LLM client (one OpenAI-compatible module with cache, rate limiter, retries and strict JSON validation), its config and tests; the live Groq call is not run yet because GROQ_API_KEY is not set.
Day 2: Claude Code built the Reader (cleaned text in, typed claims with exact quotes out, strict validation) and ran it on a fixed sample of 20 xz-devel messages.
Day 2: Claude Code hand-checked the 20 results (one clear miss, no invented quotes), ran the three prompt-injection messages live, and recorded only the measured numbers.
