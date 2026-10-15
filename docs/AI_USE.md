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
Day 2: Claude Code froze the Reader (version 1) before labelling, built the test-set rule, the labelling-sheet generator, the runner and the scorer with their guards, and found that the rule cannot give 15 messages for 2023.
Day 2: Claude Code searched xz git history and the GitHub cache for grant records (none), ran the frozen Reader on 94 of 240 xz-devel messages until the daily token limit, built the Pressure and Vouch detectors with hand-worked tests, the claim writer, the quarterly status and decision files, the replay, the demo and a read-only React page. A Haiku 5.5 subagent gave a blind AI second opinion on the test-set labels (not a human label, not ground truth).
Day 2: Claude Code ran the synthetic tallowdate case through the loader, normal metrics, detector and takeover checks, decision policy and demo script; every value not in a saved result reads NOT COMPUTED, and nothing was tuned to the answer.
Oct 12: Claude Code (Haiku 5.5, agent writeup) drafted README.md, docs/submission_checklist.md and docs/blog_outline.md from the three result files, and checked every number against its source file with a script (82 numbers, none without a source).
Oct 12: Claude Code (Haiku 5.5) wrote docs/judge_guide.md, checked each README make command against the Makefile and make.ps1, and removed the 16 README command names that are placeholders or not in the Makefile.
Oct 12: Claude Code (Haiku 5.5, agent video) wrote eval/video_check.py and docs/video/, recorded eval/results/video_quotes.json and video_numbers.json.

Oct 12: Claude Code (Haiku 5.5, block A) built the web-inbox note loop: core/agents/ (liaison, investigator, why, routing, digest, simulate_fix, inbox_graph) and api/inbox_actions.py, with tests in tests/unit/test_inbox_rules.py and tests/integration/test_inbox_loop.py and test_why_quote_link.py.
Oct 12: Claude Code (Haiku 5.5, block A) wrote ui/src/Thread.tsx and mounted it in ui/src/Inbox.tsx; clicked every inbox control in BrowserOS neo against the local app and recorded eval/results/inbox_browser_check.json and eval/results/inbox_screens/.
Oct 12: Claude Code (Haiku 5.5, block A) wrote docs/decisions/0008-inbox-no-llm.md (status OPEN): thread questions use a tool router, no LLM, because the Groq allowance is used up.
Oct 12: Claude Code (Sonnet 5.5, block A) added the session real-graph guard (tests/real_graph_guard.py, tests/conftest.py) and re-took the inbox browser evidence on commit f0025bb in BrowserOS neo.

Oct 12: Claude Code (Haiku 5.5, block d) added the action boundary (spec 4.4) with a static scan for outbound writes, the OSS pack definition (privileges, normal path, claim vocabulary) with a test that core imports nothing from packs, and the trust-path query (spec 7.6) with hand-worked tests on real FalkorDB.
Oct 12: Claude Code (Haiku 5.5, block d) added who-saw-what edges and already_acknowledged(), the source-record to grant-edge mapping (documented sources only, xz stays empty), and conflict links that call the frozen conflict policy unchanged.
Oct 12: Claude Code (Haiku 5.5, block d) ran the trust path on the tallowdate case (all NOT COMPUTED: no grant record), re-marked rows 20 and 28 DONE and rows 34, 37, 55, 72, 74 PARTIAL with their evidence, and wrote eval/results/blockers_d.md for the learning, playbook, Watcher, SHARES, Place, vector index and Foundation rows.
Oct 12: Claude Code (Haiku 5.5, block B) added make gaps CASE=xz (eval/gaps_report.py), extended make demo with gaps, hardening and tallowdate summaries from saved files, and generated docs/queries.md from the query constants with a test that it matches the code.
Oct 12: Claude Code (Haiku 5.5, block B) built the connect-your-repo flow (packs/oss/connect_repo.py, API routes, one live read of octocat/Hello-World, eval/results/connect_repo_run.json), the trust map export, the UI screens with vitest tests and a browser click-through (eval/results/ui_check_b.json), and made ecosystem and xz ingest tests skip with a reason when git-ignored data is absent.
Oct 12: Claude Code (Haiku 5.5, block B) re-marked block B rows in eval/completion_updates/block_b.py from their evidence, and made salt- and data-dependent tests skip with a reason in a clean clone.
Oct 12: Claude Code (Haiku 5.5, block B) changed the slack preview test to compare the decision stamp as a timestamp and the content without it, and added a fresh-clone first step to the README.
Oct 13: Claude Code (Haiku 5.5, block C) replayed block C's red-team and hardening commits without e0f53c9, rebuilt org_xz and org_tallowdate on an isolated FalkorDB (port 6381), reran the four red-team and hardening outputs (N 200, seed 7), and wrote eval/results/real_graph_integrity.md (status RESOLVED: counts equal the saved baseline).
Oct 15: Claude Code (Opus 5.5, design/overhaul) studied current Awwwards Site-of-the-Day winners in BrowserOS neo, wrote docs/design/direction.md and system.md (plus show_craft.md and copy_guide.md), and built demo/index.html with demo/build_demo.py, which embeds eval/results files verbatim and checks every on-screen value against them; no detector, policy, test or result changed.
