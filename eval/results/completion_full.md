# Full-project completion (measured)

Total rows 131: DONE 23, PARTIAL 40, NOT STARTED 68. Score 32.8% (DONE = 1, PARTIAL = 0.5, NOT STARTED = 0).

Rubric: DONE = built to what the spec row says and tested or measured. PARTIAL = something real exists but the row is not fully met. NOT STARTED = no code, file or result. Evidence is a file or commit in this repo.

| # | Spec | Item | Status | Evidence |
|---|---|---|---|---|
| 1 | §1 R2/R3 | FalkorDB load-bearing, image pinned to 6.0.2 | DONE | docker-compose.yml; a5711b5 |
| 2 | §1 R6 | Public or synthetic data only; identifiers hashed on ingest | DONE | core/graph/hashing.py; 09c776c |
| 3 | §1 R10 | Public repo | NOT STARTED | repo is local only, no remote |
| 4 | §1 R10 | README with setup and graph data model | PARTIAL | README.md (59c5e87): setup and model, no final judge path |
| 5 | §1 R10 | The Cypher queries the product depends on, documented | PARTIAL | README.md key queries; eval/results/*_status.json hold queries as run |
| 6 | §1 R10 | Live deployment or complete local setup | PARTIAL | README.md setup runs what exists |
| 7 | §1 R11 | AI assistance disclosure | DONE | docs/AI_USE.md; README.md AI disclosure |
| 8 | §1 R12/13 | Named module owners; design decisions recorded | PARTIAL | docs/decisions/0001-0006; no named owners |
| 9 | §1 R5 | Tracks named in the submission | PARTIAL | README.md names Track 02 (Tracks section); the submission itself is not made |
| 10 | §2.2 | Takeover cost (SPpaths) on hand-built graphs | DONE | core/takeover/cost.py; ef68035 |
| 11 | §2.2 | Takeover cost on real xz over time | NOT STARTED | eval/results/xz_takeover_status.json: NOT COMPUTED (no grant data) |
| 12 | §2.2/7.4 | Guardians (maxFlow min-cut) on hand-built graphs | DONE | core/takeover/guardians.py; ef68035 |
| 13 | §2.2 | Outsider edge rule (spec TRUSTS vs built) settled | PARTIAL | docs/decisions/0001 PROPOSED |
| 14 | §2.3/3.1 | Ecosystem records ingested for the six public places (oss-fuzz, LKML, Debian, Launchpad) | DONE | packs/oss/ecosystem/fetch.py; eval/results/ecosystem_sources.json: oss-fuzz, LKML, Debian, Launchpad all 200 with a body; xz git, GitHub and xz-devel already cached |
| 15 | §3.1 | Incident data for event-stream and axios ingested | NOT STARTED | none in data/raw/ |
| 16 | §3.5 | `tallowdate` synthetic case generated | DONE | redteam/tallowdate.py (seeded), data/synthetic/tallowdate.json, redteam/load_tallowdate.py; tests/integration/test_tallowdate_*.py |
| 17 | §4.2 | Core free of domain code; OSS pack and finance pack separated | PARTIAL | packs/oss exists; packs/finance empty |
| 18 | §4.2 | `make verify-packs` (finance runs with OSS pack removed) | NOT STARTED | target not built |
| 19 | §4.2 | OSS pack: parsers for GitHub, npm, mailing lists, bug trackers | PARTIAL | git, GitHub and mail parsers (f5d741a, 09c776c); npm and trackers none |
| 20 | §4.2 | OSS pack: privileges, normal path, claim vocabulary | PARTIAL | claim vocabulary and normal path yes; no Privilege/grant data |
| 21 | §4.2 | Finance pack (parsers, mapping, vocabulary, normal path) | NOT STARTED | packs/finance empty |
| 22 | §4.3 | Maintainer private note | NOT STARTED | no Liaison, no note code |
| 23 | §4.3 | Downstream packager question via MCP or web | NOT STARTED | no MCP, no web app |
| 24 | §4.3 | Foundation view across projects (Could) | NOT STARTED | none |
| 25 | §4.3 | Controller note with Mark callback done (finance) | NOT STARTED | none |
| 26 | §4.3 | Coding agent `check_trust` before a merge | NOT STARTED | no MCP server |
| 27 | §4.3 | Judge connects own GitHub repo, sees cost in about a minute | NOT STARTED | none |
| 28 | §4.4 | Action boundary levels 0-2 enforced; never-list enforced | PARTIAL | read-only graph guard (2483a41); no sender exists |
| 29 | §4.5 | Ethics by design: hashed ids, private only, aggregate census, situations not people | PARTIAL | hashing and read-only guard done; notes and census not built |
| 30 | §5.1 | FalkorDB capabilities verified and recorded | DONE | docs/VERIFIED.md; a5711b5 |
| 31 | §5.2 | One graph per organisation; GRAPH.COPY works | DONE | org_xz; core/graph/client.py copy; a5711b5 |
| 32 | §6.1 | org graph: Org, Actor, Action, DID, Path, VIA, Normal, OF | DONE | packs/oss/xz_graph.py; 09c776c |
| 33 | §6.1 | org graph: Source, Span, Claim, FROM, ASSERTED | DONE | core/claims/graph_write.py; 086a5e2 |
| 34 | §6.1 | org graph: Privilege, GRANTED, CAN_GRANT, APPROVED | PARTIAL | used by detectors on fixtures; none on real xz |
| 35 | §6.1 | org graph: Place, PARTICIPATES_IN, RECORDED_IN | NOT STARTED | not written anywhere |
| 36 | §6.1 | org graph: SHARES edges built | NOT STARTED | no builder; decision 0004 |
| 37 | §6.1 | org graph: CONTRADICTS / SUPERSEDES / QUALIFIES written | NOT STARTED | conflict policy computes, no edges written |
| 38 | §6.1 | org graph: Finding, Gap, Objection, Request, Note, Draft, OwnerDecision, BACKUP | NOT STARTED | none |
| 39 | §6.1 | org graph: Hardening, Task, AgentStep | NOT STARTED | none |
| 40 | §6.2 | ecosystem_<id> graph | PARTIAL | packs/oss/ecosystem/graph.py; eval/results/ecosystem_load.json: ecosystem_xz, 43 events, second load identical; no Foundation, HOSTED_BY or Campaign |
| 41 | §6.3 | redteam_<run> and harden_<run> graphs | PARTIAL | harden_<run> by GRAPH.COPY in core/hardening/simulate.py; no redteam_<run> |
| 42 | §6.4 | census_<date> graph | NOT STARTED | none |
| 43 | §6.5 | playbook graph | NOT STARTED | core/playbook is empty |
| 44 | §6.6 | Unique constraints and range indexes | DONE | core/graph/schema.py; 2483a41 |
| 45 | §6.6 | Vector index on Span and full-text index on Span.text | NOT STARTED | schema.py has neither |
| 46 | §7.1 | Pressure detector | PARTIAL | core/detectors/pressure.py; keeper condition OPEN (0005) |
| 47 | §7.1 | Vouch detector | PARTIAL | core/detectors/vouch.py; no target, no SHARES (0004) |
| 48 | §7.1 | Rush detector | DONE | core/detectors/rush.py; e0535ef |
| 49 | §7.1 | Bypass detector | DONE | core/detectors/bypass.py; e0535ef, 2e9054f |
| 50 | §7.1 | Lone keeper multiplier | PARTIAL | core/detectors/lone_keeper.py; rule PROPOSED (0001) |
| 51 | §7.1 | Detectors give a computed result on real xz | NOT STARTED | eval/results/xz_quarterly_status.json: all NOT COMPUTED / NOT_FIRED on partial reads |
| 52 | §7.2 | Conflict policy | DONE | core/policy/conflict.py; 2e9054f |
| 53 | §7.3 | Decision policy (frozen decide()) | DONE | core/policy/decision.py; 6d3f62d, 2e9054f |
| 54 | §7.5 | Visibility gaps (UNREACHABLE / UNNOTICED) | DONE | packs/oss/ecosystem/gaps.py runs the §7.5 query as written; eval/results/ecosystem_gaps.json: 4 decisions computed, 22 gap rows (a lower bound); tests/integration/test_ecosystem_xz.py |
| 55 | §7.6 | Trust path query (SPpaths from a young actor) | NOT STARTED | none |
| 56 | §7.6 | `why` query (finding to quote and link) | NOT STARTED | no Finding nodes |
| 57 | §7.6 | Read-path guard (RO_QUERY, timeout, write block, LIMIT cap) | DONE | core/graph/ro_guard.py; 2483a41 |
| 58 | §7 | As-of-T helper; no future leakage | DONE | core/graph/as_of.py; tests/integration/test_as_of.py |
| 59 | §8.1 | Watcher (idempotent ingest, normals, SHARES, visibility) | PARTIAL | ingest and normals as scripts; no worker, no SHARES, no visibility |
| 60 | §8.1 | Reader (strict JSON, validation, injection test) | DONE | core/claims/reader.py; 5c51df4; tests/injection |
| 61 | §8.1 | Investigator | NOT STARTED | core/agents is empty |
| 62 | §8.1 | Skeptic | NOT STARTED | none |
| 63 | §8.1 | Liaison | NOT STARTED | none |
| 64 | §8.1 | Red Team generator | PARTIAL | redteam/tallowdate.py: one seeded synthetic campaign with planted flags; no parameterised generator, no N or SEED |
| 65 | §8.2 | Task board with leases, stale-result rejection, requests | NOT STARTED | core/board is empty |
| 66 | §8.3 | Learned exceptions with safety rules and regression gate | NOT STARTED | core/learning is empty |
| 67 | §8.4 | LLM client: models config, rate limiter, retries, cache | DONE | core/llm/client.py; 22ea2cd, 018aab7 |
| 68 | §8.4 | Compiled plans | NOT STARTED | none |
| 69 | §8.4 | Guardrails: circuit breaker, bounded HOLD, re-plan limits | NOT STARTED | none |
| 70 | §8.5 | Hardening simulator (up to three steps, measured) | PARTIAL | core/hardening/simulate.py, eval/results/hardening_fixture.json: cost and guardians before and after on fixtures; caught and lead time not run |
| 71 | §9 | Episodic memory, every query as of T | DONE | core/graph/as_of.py |
| 72 | §9 | Semantic claims linked to spans, contradictions resolved by policy | PARTIAL | claims and spans written; no contradiction links |
| 73 | §9 | Procedural: remembered normal | PARTIAL | 3 of 6 metrics computed on xz (eval/results/xz_normal.json) |
| 74 | §9 | Who-saw-what memory | PARTIAL | WATCHES and ACTIVE_IN in ecosystem_xz; no PARTICIPATES_IN in org graphs |
| 75 | §9 | Owner memory | NOT STARTED | none |
| 76 | §9 | Working memory (AgentStep, task board) | NOT STARTED | none |
| 77 | §10.1 | Freeze protocol: dated spec published with hash; `make verify-frozen` | PARTIAL | docs/FREEZE.md is a DRAFT, hash in FREEZE.sha256; target not built; Reader frozen b6e3b1c |
| 78 | §10.2 | Memory ablation (`make ablation-memory`) | NOT STARTED | target not built |
| 79 | §10.2 | Determinism, race and concurrency tests | NOT STARTED | tests/determinism, tests/race empty |
| 80 | §10.2 | Learning proof (`verify-learning`, `chaos`) | NOT STARTED | none |
| 81 | §10.2 | Resilience (`make faults`) | NOT STARTED | tests/faults is empty |
| 82 | §10.2 | Algorithm ablation (`make ablation-algos`) | NOT STARTED | none |
| 83 | §10.2 | xz replay (`make replay CASE=xz`) | PARTIAL | eval/replay_xz.py; 59c5e87: runs, but no detector fires and 146 messages unread |
| 84 | §10.2 | event-stream and axios replays | NOT STARTED | none |
| 85 | §10.2 | Hardening on xz and 10 false-alarm projects (`make harden`) | PARTIAL | core/hardening/xz.py, eval/results/xz_hardening.json: all NOT COMPUTED on xz; no false-alarm projects |
| 86 | §10.2 | Ownership accuracy on about 30 projects (`make verify-ownership`) | NOT STARTED | none |
| 87 | §10.2 | Visibility gaps on xz (`make gaps CASE=xz`) | PARTIAL | `make ecosystem-xz` computes them (eval/ecosystem_xz.py); the `gaps CASE=xz` target is still a placeholder |
| 88 | §10.2 | Takeover Cost Census (`make census N=100`) | NOT STARTED | none |
| 89 | §10.2 | False-alarm study, about 30 projects, one demo decoy | NOT STARTED | none |
| 90 | §10.2 | Reader eval: about 100 hand-labelled spans (`make eval-reader`) | PARTIAL | 20-message spot check, 60-message test set and scorer built; no human labels yet |
| 91 | §10.3 | `make redteam N=200 SEED=...` | NOT STARTED | none |
| 92 | §10.3 | `make smoke-algos` | DONE | tests/integration/test_smoke_algos.py; a5711b5 |
| 93 | §10.3 | `make demo` with no key | PARTIAL | eval/demo.py; prints the replay table only |
| 94 | §11.1 | Finance pack case (Northbridge, Kestrel), scripted | NOT STARTED | none |
| 95 | §11.2 | Takeover Cost Census ingest (npm, structure only) | NOT STARTED | none |
| 96 | §12.1 | hearthguard-core MCP server (9 tools) | NOT STARTED | mcp_servers/ is empty |
| 97 | §12.1 | pack-oss MCP server | NOT STARTED | none |
| 98 | §12.1 | pack-finance MCP server | NOT STARTED | none |
| 99 | §12.1 | FalkorDB MCP wired read-only; Claude Code check_trust demo | NOT STARTED | none |
| 100 | §12.2 | Slack app (Bolt, Socket Mode) sends the note | PARTIAL | slack_app/render.py renders the note (eval/results/slack_preview.json, sent_to_slack false); no Bolt, nothing sent |
| 101 | §12.2 | Show me why button | PARTIAL | slack_app/show_why.py and api /api/notes/{quarter}/why, from saved results; not in Slack |
| 102 | §12.2 | Simulate a fix button | PARTIAL | api /api/notes/{quarter}/simulate reads eval/results/xz_hardening.json; not run live, not in Slack |
| 103 | §12.2 | Draft a reply button | NOT STARTED | none |
| 104 | §12.2 | It's fine button and learning result in thread | PARTIAL | api dismiss writes a local JSONL file; no OwnerDecision, no learned exception |
| 105 | §12.2 | Thread questions answered from tools | NOT STARTED | none |
| 106 | §12.2 | Availability routing to the named backup; shared thread for two keepers | NOT STARTED | none |
| 107 | §12.2 | Weekly digest | NOT STARTED | none |
| 108 | §12.2 | Slash commands (Could) | NOT STARTED | none |
| 109 | §12.2 | Slack safety tests: injection, double tap, Slack down | NOT STARTED | none |
| 110 | §12.2 | Web inbox fallback | PARTIAL | api/app.py, ui/src/Inbox.tsx: note, why, simulate, dismiss; no thread questions |
| 111 | §13.1 | Replay timeline | PARTIAL | ui/ replay table over eval/results; no chart or markers |
| 112 | §13.2 | Who saw what | NOT STARTED | none |
| 113 | §13.3 | Takeover cost gauge | NOT STARTED | none |
| 114 | §13.4 | Trust map (Cytoscape) | NOT STARTED | none |
| 115 | §13.5 | Evidence card | PARTIAL | ui/ shows status, reason, query text and time; no checklist or quotes |
| 116 | §13.6 | Hardening simulator screen | NOT STARTED | none |
| 117 | §13.7 | Patience curve | NOT STARTED | none |
| 118 | §13.8 | Connect your repo | NOT STARTED | none |
| 119 | §13.9 | Census screen | NOT STARTED | none |
| 120 | §13.10 | Playbook screen | NOT STARTED | none |
| 121 | §13.11 | Inbox screen | PARTIAL | ui/src/Inbox.tsx over api/app.py; no thread |
| 122 | §13.12 | Two endings screen | NOT STARTED | none |
| 123 | §13 | Pack header and synthetic labels on every screen | PARTIAL | ui/ labels its data source; no pack header |
| 124 | §15 Could | Discord and email front ends | NOT STARTED | none |
| 125 | §15 Could | Vector search for similar pressure messages | NOT STARTED | none |
| 126 | §15 Could | Non-English pressure detection | NOT STARTED | none |
| 127 | §15 Must | Three real-maintainer reactions, with consent | NOT STARTED | none |
| 128 | Pitch | README, final (claim, commands, model, queries, measured, limits, AI use) | PARTIAL | README.md 59c5e87; no video link, tracks or full command list |
| 129 | Pitch | Demo video, 3 minutes (§14) | NOT STARTED | docs/video/shot_list.md and narration.md are a script; eval/video_check.py checks numbers; no video exists |
| 130 | Pitch | Blog post (§20) | PARTIAL | docs/blog/post.md written (1,519 words) with eval/blog_check.py; not published, not linked from the README |
| 131 | Pitch | Submission form and track mapping (§19) | NOT STARTED | docs/submission_checklist.md lists what is needed; the form is not filled |
