# Remaining rows not assigned to an agent block

Open rows on main: 80 (PARTIAL or NOT STARTED). Agent-doable: 33. Set aside: 47.
Each row has one reason it is not agent work now. Rows come from eval/results/completion_full.md.

| Row | Item | Reason |
|---|---|---|
| 3 | Public repo | publishing to a remote is outward-facing; a person decides when to publish |
| 8 | Named module owners; design decisions recorded | named module owners need the team's names (R12/R13); an agent cannot assign people |
| 9 | Tracks named in the submission | the submission is a person's action; the rows only name tracks in the form |
| 11 | Takeover cost on real xz over time | takeover cost on real xz needs grant data that does not exist publicly; stays NOT COMPUTED |
| 13 | Outsider edge rule (spec TRUSTS vs built) settled | the outsider edge rule is a design decision for the team (0001 PROPOSED) |
| 22 | Maintainer private note | the Slack DM needs a Slack workspace and bot credentials (external accounts) |
| 24 | Foundation view across projects (Could) | Could item: a foundation view needs multi-project data not in the repo |
| 25 | Controller note with Mark callback done (finance) | the controller note is a Slack DM (same dependency as row 22) |
| 26 | Coding agent `check_trust` before a merge | the demo needs a live coding-agent session calling check_trust; the tool itself is row 96 |
| 29 | Ethics by design: hashed ids, private only, aggregate census, situations not people | needs the census (rows 42, 88, 95) and the Slack note path (row 22) |
| 34 | org graph: Privilege, GRANTED, CAN_GRANT, APPROVED | no documented grant record exists for xz; needs grant data that does not exist publicly |
| 36 | org graph: SHARES edges built | domain_hash needs email domains the cache hashes away; creation_window needs account data |
| 37 | org graph: CONTRADICTS / SUPERSEDES / QUALIFIES written | the spec defines no rule for finding contradicting pairs; needs a team decision (7.2 frozen) |
| 38 | org graph: Finding, Gap, Objection, Request, Note, Draft, OwnerDecision, BACKUP | Objection and Request need the Skeptic, an LLM agent; LLM allowance is used up |
| 42 | census_<date> graph | the census package list is not frozen (10.1) and cannot be frozen after the fact |
| 46 | Pressure detector | the Pressure keeper-activity condition is open in the frozen spec (decision 0005) |
| 47 | Vouch detector | Vouch needs SHARES edges (row 36), which are set aside |
| 50 | Lone keeper multiplier | the Lone keeper rule is PROPOSED (decision 0001); needs a team decision |
| 51 | Detectors give a computed result on real xz | needs the full Reader run; LLM allowance is used up until it resets |
| 55 | Trust path query (SPpaths from a young actor) | the synthetic tallowdate case has no grant record; adding one changes published results (team decision) |
| 59 | Watcher (idempotent ingest, normals, SHARES, visibility) | the Watcher needs SHARES (row 36), which is set aside |
| 61 | Investigator | the Investigator's LLM planner needs the LLM; allowance is used up (ADR 0008 OPEN) |
| 62 | Skeptic | the Skeptic is an LLM benign-explanation search; LLM allowance is used up |
| 63 | Liaison | the Liaison's LLM wording and the Slack sender need the LLM and Slack |
| 68 | Compiled plans | compiled plans are saved from LLM-planned tasks (row 61), which is set aside |
| 72 | Semantic claims linked to spans, contradictions resolved by policy | same as row 37: no rule for finding contradicting pairs in the spec |
| 73 | Procedural: remembered normal | keeper_activity depends on open decision 0005; grant_days and trusted_actor_set need grant data |
| 77 | Freeze protocol: dated spec published with hash; `make verify-frozen` | docs/FREEZE.md is a draft; a dated freeze is the team's, and CLAUDE.md bars editing freeze files unasked |
| 83 | xz replay (`make replay CASE=xz`) | the xz replay needs the full Reader run (146 messages unread); LLM allowance is used up |
| 85 | Hardening on xz and 10 false-alarm projects (`make harden`) | the 10 false-alarm projects need the frozen selection list (10.1), which is not published |
| 86 | Ownership accuracy on about 30 projects (`make verify-ownership`) | ownership accuracy needs the frozen project list (10.1, 10.2), which is not published |
| 88 | Takeover Cost Census (`make census N=100`) | the census command needs the frozen package list (row 42) |
| 89 | False-alarm study, about 30 projects, one demo decoy | the false-alarm study needs the frozen project list (row 85) |
| 90 | Reader eval: about 100 hand-labelled spans (`make eval-reader`) | about 100 hand-labelled spans need human labels |
| 95 | Takeover Cost Census ingest (npm, structure only) | the census ingest needs the frozen package list (row 42) |
| 99 | FalkorDB MCP wired read-only; Claude Code check_trust demo | needs the official FalkorDB MCP package and a live Claude Code session for the demo |
| 100 | Slack app (Bolt, Socket Mode) sends the note | the Slack app needs a Slack workspace and tokens (row 22) |
| 108 | Slash commands (Could) | Could item: slash commands need Slack (row 22) |
| 109 | Slack safety tests: injection, double tap, Slack down | the Slack-down test needs Slack code (row 22) |
| 119 | Census screen | the census screen needs census data (row 42) |
| 124 | Discord and email front ends | Could item: Discord and email front ends need external accounts |
| 125 | Vector search for similar pressure messages | Could item: vector similarity search; deferred until row 45 (block H) is merged |
| 126 | Non-English pressure detection | Could item: non-English detection needs the Reader LLM; allowance is used up |
| 127 | Three real-maintainer reactions, with consent | needs three real maintainers' consent; outside the team's control |
| 129 | Demo video, 3 minutes (§14) | the demo video needs a person to record it (under 3 minutes) |
| 130 | Blog post (§20) | publishing the blog is outward-facing; a person decides |
| 131 | Submission form and track mapping (§19) | the submission form is filled in by a person |
