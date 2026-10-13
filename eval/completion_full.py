"""Measured completion of the whole Hearthguard project against docs/HEARTHGUARD.md.

Run: python -m eval.completion_full
Writes eval/results/completion_full.md (the table) and completion_full.json (the counts).
Each row is one feature, module, screen, command, test or deliverable the spec describes, plus the
pitch deliverables. Status is DONE (1), PARTIAL (0.5) or NOT STARTED (0). The evidence column
names a file or commit. The score is computed from the rows below, never typed.
Rubric: DONE = built to what the spec row says and tested or measured; PARTIAL = something
real exists but the row's claim is not fully met; NOT STARTED = no code, file or result.
A module that works on hand-built graphs but cannot be computed on real data is PARTIAL only
when the spec row itself asks for the real-data result.
"""

import json
from pathlib import Path

D, P, N = "DONE", "PARTIAL", "NOT STARTED"
RESULTS = Path(__file__).resolve().parent / "results"

# (spec ref, item, status, evidence)
ROWS = [
    # ---- §1 constraints and required submission contents
    ("§1 R2/R3", "FalkorDB load-bearing, image pinned to 6.0.2", D, "docker-compose.yml; a5711b5"),
    (
        "§1 R6",
        "Public or synthetic data only; identifiers hashed on ingest",
        D,
        "core/graph/hashing.py; 09c776c",
    ),
    ("§1 R10", "Public repo", N, "repo is local only, no remote"),
    (
        "§1 R10",
        "README with setup and graph data model",
        P,
        "README.md (59c5e87): setup and model, no final judge path",
    ),
    (
        "§1 R10",
        "The Cypher queries the product depends on, documented",
        P,
        "README.md key queries; eval/results/*_status.json hold queries as run",
    ),
    ("§1 R10", "Live deployment or complete local setup", P, "README.md setup runs what exists"),
    ("§1 R11", "AI assistance disclosure", D, "docs/AI_USE.md; README.md AI disclosure"),
    (
        "§1 R12/13",
        "Named module owners; design decisions recorded",
        P,
        "docs/decisions/0001-0006; no named owners",
    ),
    ("§1 R5", "Tracks named in the submission", N, "no track statement in README"),
    # ---- §2 and §3 the idea and the stories
    ("§2.2", "Takeover cost (SPpaths) on hand-built graphs", D, "core/takeover/cost.py; ef68035"),
    (
        "§2.2",
        "Takeover cost on real xz over time",
        N,
        "eval/results/xz_takeover_status.json: NOT COMPUTED (no grant data)",
    ),
    (
        "§2.2/7.4",
        "Guardians (maxFlow min-cut) on hand-built graphs",
        D,
        "core/takeover/guardians.py; ef68035",
    ),
    (
        "§2.2",
        "Outsider edge rule (spec TRUSTS vs built) settled",
        P,
        "docs/decisions/0001 PROPOSED",
    ),
    (
        "§2.3/3.1",
        "Ecosystem records ingested for the six public places (oss-fuzz, LKML, Debian, Launchpad)",
        N,
        "only xz git, GitHub and xz-devel are cached",
    ),
    ("§3.1", "Incident data for event-stream and axios ingested", N, "none in data/raw/"),
    ("§3.5", "`tallowdate` synthetic case generated", N, "redteam/ is empty"),
    # ---- §4 product
    (
        "§4.2",
        "Core free of domain code; OSS pack and finance pack separated",
        P,
        "packs/oss exists; packs/finance empty",
    ),
    ("§4.2", "`make verify-packs` (finance runs with OSS pack removed)", N, "target not built"),
    (
        "§4.2",
        "OSS pack: parsers for GitHub, npm, mailing lists, bug trackers",
        P,
        "git, GitHub and mail parsers (f5d741a, 09c776c); npm and trackers none",
    ),
    (
        "§4.2",
        "OSS pack: privileges, normal path, claim vocabulary",
        P,
        "claim vocabulary and normal path yes; no Privilege/grant data",
    ),
    ("§4.2", "Finance pack (parsers, mapping, vocabulary, normal path)", N, "packs/finance empty"),
    ("§4.3", "Maintainer private note", N, "no Liaison, no note code"),
    ("§4.3", "Downstream packager question via MCP or web", N, "no MCP, no web app"),
    ("§4.3", "Foundation view across projects (Could)", N, "none"),
    ("§4.3", "Controller note with Mark callback done (finance)", N, "none"),
    ("§4.3", "Coding agent `check_trust` before a merge", N, "no MCP server"),
    ("§4.3", "Judge connects own GitHub repo, sees cost in about a minute", N, "none"),
    (
        "§4.4",
        "Action boundary levels 0-2 enforced; never-list enforced",
        P,
        "read-only graph guard (2483a41); no sender exists",
    ),
    (
        "§4.5",
        "Ethics by design: hashed ids, private only, aggregate census, situations not people",
        P,
        "hashing and read-only guard done; notes and census not built",
    ),
    # ---- §5 architecture
    ("§5.1", "FalkorDB capabilities verified and recorded", D, "docs/VERIFIED.md; a5711b5"),
    (
        "§5.2",
        "One graph per organisation; GRAPH.COPY works",
        D,
        "org_xz; core/graph/client.py copy; a5711b5",
    ),
    # ---- §6 graph model
    (
        "§6.1",
        "org graph: Org, Actor, Action, DID, Path, VIA, Normal, OF",
        D,
        "packs/oss/xz_graph.py; 09c776c",
    ),
    (
        "§6.1",
        "org graph: Source, Span, Claim, FROM, ASSERTED",
        D,
        "core/claims/graph_write.py; 086a5e2",
    ),
    (
        "§6.1",
        "org graph: Privilege, GRANTED, CAN_GRANT, APPROVED",
        P,
        "used by detectors on fixtures; none on real xz",
    ),
    ("§6.1", "org graph: Place, PARTICIPATES_IN, RECORDED_IN", N, "not written anywhere"),
    ("§6.1", "org graph: SHARES edges built", N, "no builder; decision 0004"),
    (
        "§6.1",
        "org graph: CONTRADICTS / SUPERSEDES / QUALIFIES written",
        N,
        "conflict policy computes, no edges written",
    ),
    (
        "§6.1",
        "org graph: Finding, Gap, Objection, Request, Note, Draft, OwnerDecision, BACKUP",
        N,
        "none",
    ),
    ("§6.1", "org graph: Hardening, Task, AgentStep", N, "none"),
    ("§6.2", "ecosystem_<id> graph", N, "none"),
    ("§6.3", "redteam_<run> and harden_<run> graphs", N, "none"),
    ("§6.4", "census_<date> graph", N, "none"),
    ("§6.5", "playbook graph", N, "core/playbook is empty"),
    ("§6.6", "Unique constraints and range indexes", D, "core/graph/schema.py; 2483a41"),
    ("§6.6", "Vector index on Span and full-text index on Span.text", N, "schema.py has neither"),
    # ---- §7 detectors and policies
    ("§7.1", "Pressure detector", P, "core/detectors/pressure.py; keeper condition OPEN (0005)"),
    ("§7.1", "Vouch detector", P, "core/detectors/vouch.py; no target, no SHARES (0004)"),
    ("§7.1", "Rush detector", D, "core/detectors/rush.py; e0535ef"),
    ("§7.1", "Bypass detector", D, "core/detectors/bypass.py; e0535ef, 2e9054f"),
    ("§7.1", "Lone keeper multiplier", P, "core/detectors/lone_keeper.py; rule PROPOSED (0001)"),
    (
        "§7.1",
        "Detectors give a computed result on real xz",
        N,
        "eval/results/xz_quarterly_status.json: all NOT COMPUTED / NOT_FIRED on partial reads",
    ),
    ("§7.2", "Conflict policy", D, "core/policy/conflict.py; 2e9054f"),
    ("§7.3", "Decision policy (frozen decide())", D, "core/policy/decision.py; 6d3f62d, 2e9054f"),
    ("§7.5", "Visibility gaps (UNREACHABLE / UNNOTICED)", N, "core/gaps is empty"),
    ("§7.6", "Trust path query (SPpaths from a young actor)", N, "none"),
    ("§7.6", "`why` query (finding to quote and link)", N, "no Finding nodes"),
    (
        "§7.6",
        "Read-path guard (RO_QUERY, timeout, write block, LIMIT cap)",
        D,
        "core/graph/ro_guard.py; 2483a41",
    ),
    (
        "§7",
        "As-of-T helper; no future leakage",
        D,
        "core/graph/as_of.py; tests/integration/test_as_of.py",
    ),
    # ---- §8 agents, coordination, learning, hardening
    (
        "§8.1",
        "Watcher (idempotent ingest, normals, SHARES, visibility)",
        P,
        "ingest and normals as scripts; no worker, no SHARES, no visibility",
    ),
    (
        "§8.1",
        "Reader (strict JSON, validation, injection test)",
        D,
        "core/claims/reader.py; 5c51df4; tests/injection",
    ),
    ("§8.1", "Investigator", N, "core/agents is empty"),
    ("§8.1", "Skeptic", N, "none"),
    ("§8.1", "Liaison", N, "none"),
    ("§8.1", "Red Team generator", N, "redteam/ is empty"),
    ("§8.2", "Task board with leases, stale-result rejection, requests", N, "core/board is empty"),
    (
        "§8.3",
        "Learned exceptions with safety rules and regression gate",
        N,
        "core/learning is empty",
    ),
    (
        "§8.4",
        "LLM client: models config, rate limiter, retries, cache",
        D,
        "core/llm/client.py; 22ea2cd, 018aab7",
    ),
    ("§8.4", "Compiled plans", N, "none"),
    ("§8.4", "Guardrails: circuit breaker, bounded HOLD, re-plan limits", N, "none"),
    ("§8.5", "Hardening simulator (up to three steps, measured)", N, "core/hardening is empty"),
    # ---- §9 memory
    ("§9", "Episodic memory, every query as of T", D, "core/graph/as_of.py"),
    (
        "§9",
        "Semantic claims linked to spans, contradictions resolved by policy",
        P,
        "claims and spans written; no contradiction links",
    ),
    (
        "§9",
        "Procedural: remembered normal",
        P,
        "3 of 6 metrics computed on xz (eval/results/xz_normal.json)",
    ),
    ("§9", "Who-saw-what memory", N, "none"),
    ("§9", "Owner memory", N, "none"),
    ("§9", "Working memory (AgentStep, task board)", N, "none"),
    # ---- §10 evaluation
    (
        "§10.1",
        "Freeze protocol: dated spec published with hash; `make verify-frozen`",
        P,
        "docs/FREEZE.md is a DRAFT, hash in FREEZE.sha256; target not built; Reader frozen b6e3b1c",
    ),
    ("§10.2", "Memory ablation (`make ablation-memory`)", N, "target not built"),
    ("§10.2", "Determinism, race and concurrency tests", N, "tests/determinism, tests/race empty"),
    ("§10.2", "Learning proof (`verify-learning`, `chaos`)", N, "none"),
    ("§10.2", "Resilience (`make faults`)", N, "tests/faults is empty"),
    ("§10.2", "Algorithm ablation (`make ablation-algos`)", N, "none"),
    (
        "§10.2",
        "xz replay (`make replay CASE=xz`)",
        P,
        "eval/replay_xz.py; 59c5e87: runs, but no detector fires and 146 messages unread",
    ),
    ("§10.2", "event-stream and axios replays", N, "none"),
    ("§10.2", "Hardening on xz and 10 false-alarm projects (`make harden`)", N, "none"),
    ("§10.2", "Ownership accuracy on about 30 projects (`make verify-ownership`)", N, "none"),
    ("§10.2", "Visibility gaps on xz (`make gaps CASE=xz`)", N, "none"),
    ("§10.2", "Takeover Cost Census (`make census N=100`)", N, "none"),
    ("§10.2", "False-alarm study, about 30 projects, one demo decoy", N, "none"),
    (
        "§10.2",
        "Reader eval: about 100 hand-labelled spans (`make eval-reader`)",
        P,
        "20-message spot check, 60-message test set and scorer built; no human labels yet",
    ),
    ("§10.3", "`make redteam N=200 SEED=...`", N, "none"),
    ("§10.3", "`make smoke-algos`", D, "tests/integration/test_smoke_algos.py; a5711b5"),
    ("§10.3", "`make demo` with no key", P, "eval/demo.py; prints the replay table only"),
    # ---- §11 second domain and census
    ("§11.1", "Finance pack case (Northbridge, Kestrel), scripted", N, "none"),
    ("§11.2", "Takeover Cost Census ingest (npm, structure only)", N, "none"),
    # ---- §12 MCP and Slack
    ("§12.1", "hearthguard-core MCP server (9 tools)", N, "mcp_servers/ is empty"),
    ("§12.1", "pack-oss MCP server", N, "none"),
    ("§12.1", "pack-finance MCP server", N, "none"),
    ("§12.1", "FalkorDB MCP wired read-only; Claude Code check_trust demo", N, "none"),
    ("§12.2", "Slack app (Bolt, Socket Mode) sends the note", N, "slack_app/ is empty"),
    ("§12.2", "Show me why button", N, "none"),
    ("§12.2", "Simulate a fix button", N, "none"),
    ("§12.2", "Draft a reply button", N, "none"),
    ("§12.2", "It's fine button and learning result in thread", N, "none"),
    ("§12.2", "Thread questions answered from tools", N, "none"),
    ("§12.2", "Availability routing to the named backup; shared thread for two keepers", N, "none"),
    ("§12.2", "Weekly digest", N, "none"),
    ("§12.2", "Slash commands (Could)", N, "none"),
    ("§12.2", "Slack safety tests: injection, double tap, Slack down", N, "none"),
    ("§12.2", "Web inbox fallback", N, "none"),
    # ---- §13 UI screens
    ("§13.1", "Replay timeline", P, "ui/ replay table over eval/results; no chart or markers"),
    ("§13.2", "Who saw what", N, "none"),
    ("§13.3", "Takeover cost gauge", N, "none"),
    ("§13.4", "Trust map (Cytoscape)", N, "none"),
    (
        "§13.5",
        "Evidence card",
        P,
        "ui/ shows status, reason, query text and time; no checklist or quotes",
    ),
    ("§13.6", "Hardening simulator screen", N, "none"),
    ("§13.7", "Patience curve", N, "none"),
    ("§13.8", "Connect your repo", N, "none"),
    ("§13.9", "Census screen", N, "none"),
    ("§13.10", "Playbook screen", N, "none"),
    ("§13.11", "Inbox screen", N, "none"),
    ("§13.12", "Two endings screen", N, "none"),
    (
        "§13",
        "Pack header and synthetic labels on every screen",
        P,
        "ui/ labels its data source; no pack header",
    ),
    # ---- §15 Could items
    ("§15 Could", "Discord and email front ends", N, "none"),
    ("§15 Could", "Vector search for similar pressure messages", N, "none"),
    ("§15 Could", "Non-English pressure detection", N, "none"),
    # ---- pitch deliverables
    ("§15 Must", "Three real-maintainer reactions, with consent", N, "none"),
    (
        "Pitch",
        "README, final (claim, commands, model, queries, measured, limits, AI use)",
        P,
        "README.md 59c5e87; no video link, tracks or full command list",
    ),
    ("Pitch", "Demo video, 3 minutes (§14)", N, "none"),
    ("Pitch", "Blog post (§20)", N, "none"),
    ("Pitch", "Submission form and track mapping (§19)", N, "none"),
]

# Re-assessment on main after merging agent/synthetic, agent/hardening, agent/slack and
# agent/writeup (merge commits c5a82c0 and earlier). Only merged work counts. Row order and row
# numbers do not change, because README.md and docs/submission_checklist.md cite them.
# item prefix -> (new status, new evidence)
UPDATES = {
    "Tracks named in the submission": (
        P,
        "README.md names Track 02 (Tracks section); the submission itself is not made",
    ),
    "`tallowdate` synthetic case generated": (
        D,
        "redteam/tallowdate.py (seeded), data/synthetic/tallowdate.json, "
        "redteam/load_tallowdate.py; tests/integration/test_tallowdate_*.py",
    ),
    "redteam_<run> and harden_<run> graphs": (
        P,
        "harden_<run> by GRAPH.COPY in core/hardening/simulate.py; no redteam_<run>",
    ),
    "Red Team generator": (
        P,
        "redteam/tallowdate.py: one seeded synthetic campaign with planted flags; "
        "no parameterised generator, no N or SEED",
    ),
    "Hardening simulator (up to three steps, measured)": (
        P,
        "core/hardening/simulate.py, eval/results/hardening_fixture.json: cost and guardians "
        "before and after on fixtures; caught and lead time not run",
    ),
    "Hardening on xz and 10 false-alarm projects": (
        P,
        "core/hardening/xz.py, eval/results/xz_hardening.json: all NOT COMPUTED on xz; "
        "no false-alarm projects",
    ),
    "Slack app (Bolt, Socket Mode) sends the note": (
        P,
        "slack_app/render.py renders the note (eval/results/slack_preview.json, "
        "sent_to_slack false); no Bolt, nothing sent",
    ),
    "Show me why button": (
        P,
        "slack_app/show_why.py and api /api/notes/{quarter}/why, from saved results; not in Slack",
    ),
    "Simulate a fix button": (
        P,
        "api /api/notes/{quarter}/simulate reads eval/results/xz_hardening.json; "
        "not run live, not in Slack",
    ),
    "It's fine button and learning result in thread": (
        P,
        "api dismiss writes a local JSONL file; no OwnerDecision, no learned exception",
    ),
    "Web inbox fallback": (
        P,
        "api/app.py, ui/src/Inbox.tsx: note, why, simulate, dismiss; no thread questions",
    ),
    "Inbox screen": (P, "ui/src/Inbox.tsx over api/app.py; no thread"),
    "Blog post (§20)": (N, "docs/blog_outline.md is an outline only; the post is not written"),
    "Submission form and track mapping": (
        N,
        "docs/submission_checklist.md lists what is needed; the form is not filled",
    ),
}


def _apply_updates(rows: list, updates: dict) -> list:
    out, used = [], set()
    for ref, item, status, ev in rows:
        for prefix, (new_status, new_ev) in updates.items():
            if item.startswith(prefix):
                status, ev = new_status, new_ev
                used.add(prefix)
        out.append((ref, item, status, ev))
    missing = set(updates) - used
    if missing:
        raise RuntimeError(f"update matches no row: {sorted(missing)}")
    return out


ROWS = _apply_updates(ROWS, UPDATES)
# Second re-assessment, on main after merging agent/ecosystem, agent/video, agent/fresh-clone and
# agent/blog. Applied after the first layer. Only merged work counts; row order is unchanged.
UPDATES_2 = {
    "Ecosystem records ingested for the six public places": (
        D,
        "packs/oss/ecosystem/fetch.py; eval/results/ecosystem_sources.json: oss-fuzz, LKML, "
        "Debian, Launchpad all 200 with a body; xz git, GitHub and xz-devel already cached",
    ),
    "ecosystem_<id> graph": (
        P,
        "packs/oss/ecosystem/graph.py; eval/results/ecosystem_load.json: ecosystem_xz, 43 "
        "events, second load identical; no Foundation, HOSTED_BY or Campaign",
    ),
    "Visibility gaps (UNREACHABLE / UNNOTICED)": (
        D,
        "packs/oss/ecosystem/gaps.py runs the §7.5 query as written; "
        "eval/results/ecosystem_gaps.json: 4 decisions computed, 22 gap rows (a lower bound); "
        "tests/integration/test_ecosystem_xz.py",
    ),
    "Visibility gaps on xz": (
        P,
        "`make ecosystem-xz` computes them (eval/ecosystem_xz.py); the `gaps CASE=xz` target "
        "is still a placeholder",
    ),
    "Who-saw-what memory": (
        P,
        "WATCHES and ACTIVE_IN in ecosystem_xz; no PARTICIPATES_IN in org graphs",
    ),
    "Blog post (§20)": (
        P,
        "docs/blog/post.md written (1,519 words) with eval/blog_check.py; not published, "
        "not linked from the README",
    ),
    "Demo video, 3 minutes": (
        N,
        "docs/video/shot_list.md and narration.md are a script; eval/video_check.py checks "
        "numbers; no video exists",
    ),
}
ROWS = _apply_updates(ROWS, UPDATES_2)
import importlib
import pkgutil


from eval import completion_updates as _cu


from eval import completion_updates as _cu

for _m in sorted(pkgutil.iter_modules(_cu.__path__), key=lambda m: m.name):
    ROWS = _apply_updates(ROWS, importlib.import_module(f"eval.completion_updates.{_m.name}").UPDATES)

PREVIOUS = {
    "total_rows": 131,
    "DONE": 20,
    "PARTIAL": 25,
    "NOT_STARTED": 86,
    "score_percent": 24.8,
    "measured_at": "00b09ea (after agent/synthetic, hardening, slack, writeup)",
}

SCORE = {D: 1.0, P: 0.5, N: 0.0}


def build() -> dict:
    counts = {D: 0, P: 0, N: 0}
    for _ref, _item, status, _ev in ROWS:
        counts[status] += 1
    total = len(ROWS)
    score = sum(SCORE[s] * n for s, n in counts.items())
    return {
        "total_rows": total,
        "DONE": counts[D],
        "PARTIAL": counts[P],
        "NOT_STARTED": counts[N],
        "score_points": score,
        "score_percent": round(100 * score / total, 1),
        "weights": {"DONE": 1, "PARTIAL": 0.5, "NOT STARTED": 0},
        "source": "docs/HEARTHGUARD.md plus pitch deliverables; rows in eval/completion_full.py",
        "previous": PREVIOUS,
    }


def table() -> str:
    lines = ["| # | Spec | Item | Status | Evidence |", "|---|---|---|---|---|"]
    for i, (ref, item, status, ev) in enumerate(ROWS, start=1):
        lines.append(f"| {i} | {ref} | {item} | {status} | {ev} |")
    return "\n".join(lines)


def main() -> int:
    c = build()
    md = [
        "# Full-project completion (measured)",
        "",
        f"Total rows {c['total_rows']}: DONE {c['DONE']}, PARTIAL {c['PARTIAL']}, "
        f"NOT STARTED {c['NOT_STARTED']}. Score {c['score_percent']}% "
        "(DONE = 1, PARTIAL = 0.5, NOT STARTED = 0).",
        "",
        "Rubric: DONE = built to what the spec row says and tested or measured. "
        "PARTIAL = something "
        "real exists but the row is not fully met. NOT STARTED = no code, file or result. "
        "Evidence is a file or commit in this repo.",
        "",
        table(),
        "",
    ]
    (RESULTS / "completion_full.md").write_text("\n".join(md), encoding="utf-8")
    (RESULTS / "completion_full.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
    print(
        f"total rows {c['total_rows']}, DONE {c['DONE']}, PARTIAL {c['PARTIAL']}, "
        f"NOT STARTED {c['NOT_STARTED']}, score {c['score_percent']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
