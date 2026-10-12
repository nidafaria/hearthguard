"""Investigator for thread questions (spec 8.1, 12.2). A fixed router over tested tools.

No model is used (docs/decisions/0008-inbox-no-llm.md). A question is matched to one tool by
fixed patterns; the answer is that tool's output with where it came from. Questions that ask for
a judgement about a person, or ask the system to approve or block someone, are refused with the
facts. A question no tool covers gets the list of what can be answered. Prompt-injection text in
a question matches none of the tool patterns, so it is answered as an unknown question or
refused, and it changes nothing.
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents import why
from core.agents.cases import CASES, Case, normalize_rows, read_json
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from core.hardening.simulate import PRIV
from core.takeover import cost, guardians

READ_MS = 10_000
DAY_S = 86_400
REVIEW_WINDOW_DAYS = 90  # same 90-day look-back as keeper activity (config/frozen.yaml)

REFUSAL = "I can't tell you whether someone is an attacker; here are the facts."
SUPPORTED = (
    "What is the takeover cost?",
    "Who are the guardians, and who could I even ask?",
    "What is normal for this project?",
    "Who reviewed changes recently?",
    "Has this happened before?",
)

_JUDGE = re.compile(
    r"\b(attacker|malicious|compromised|bad actor|trustworthy|guilty|culprit|hacker|impostor|"
    r"liar|scammer|spy|sockpuppet|sock puppet|fake account|evil)\b|"
    r"\b(can|should|do) i trust\b|\bis (he|she|they|it|[a-z]+) (safe|honest|legit|lying|real)\b",
    re.IGNORECASE,
)
_ACT = re.compile(
    r"\b(approve|reject|ban|block|revoke|grant|ignore (your|the|all|previous)|"
    r"disregard|override|forget your)\b",
    re.IGNORECASE,
)
_HISTORY = re.compile(
    r"happened before|seen (this )?before|precedent|ever happened|history of", re.I
)
_COST = re.compile(r"takeover cost|cost to take|how (hard|easy) .*take|how many approvals", re.I)
_GUARD = re.compile(
    r"guardian|who (can|could|do) (i )?(even )?(ask|help|release|publish|approve)|"
    r"who (holds|has) (release|publish)|second keeper|co-?maintainer|who can publish",
    re.I,
)
_REVIEW = re.compile(r"who reviewed|reviewers?|\breviewed\b", re.I)
_NORMAL = re.compile(r"\bnormal\b|usual|typical|cadence|baseline|how active", re.I)


@dataclass
class Answer:
    tool: str
    text: str
    refused: bool = False
    links: list[dict] = field(default_factory=list)
    queries: list[dict] = field(default_factory=list)
    ms: float = 0.0


def normalize_question(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def route(question: str) -> str:
    """Which tool answers this question. Fixed patterns, checked in this order."""
    if _JUDGE.search(question) or _ACT.search(question):
        return "refuse"
    for tool, rx in (
        ("history", _HISTORY),
        ("takeover_cost", _COST),
        ("guardians", _GUARD),
        ("who_reviewed", _REVIEW),
        ("normal", _NORMAL),
    ):
        if rx.search(question):
            return tool
    return "unsupported"


def _short(hid: str) -> str:
    return hid[:8]


def _file_link(name: str) -> dict:
    return {"label": f"eval/results/{name}", "ref": f"eval/results/{name}"}


def _refuse(case: Case, row: dict, results: Path, question: str) -> Answer:
    lines = [REFUSAL]
    links = []
    for f in why.saved_facts(case, row, results):
        lines.append(f"- {f['fact'].replace('_', ' ').title()}: {f['status']}. {f['reason']}")
        if f["file"]:
            links.append(_file_link(f["file"]))
    lines.append(
        "I do not approve, block or judge anyone. You decide; I can answer: " + " ".join(SUPPORTED)
    )
    return Answer("refuse", "\n".join(lines), refused=True, links=_dedupe(links))


def _dedupe(links: list[dict]) -> list[dict]:
    seen, out = set(), []
    for item in links:
        if item["ref"] not in seen:
            seen.add(item["ref"])
            out.append(item)
    return out


def _takeover(client: FalkorClient, case: Case, row: dict) -> Answer:
    r = cost.takeover_cost(client, case.org, PRIV, row["T"])
    if r.status == cost.COMPUTED:
        text = (
            f"Takeover cost as of {row['T_iso']}: {r.cost} approvals an outsider would need "
            "(PROPOSED rule, provisional)."
        )
    else:
        text = f"Takeover cost as of {row['T_iso']}: {r.status}. {r.reason}"
    return Answer(
        "takeover_cost",
        text,
        links=[_file_link("xz_takeover_status.json")] if not case.synthetic else [],
        queries=list(r.queries),
        ms=r.query_ms or 0.0,
    )


def _guardians(client: FalkorClient, case: Case, row: dict) -> Answer:
    g = guardians.guardians(client, case.org, PRIV, row["T"])
    keepers = ig.keepers_as_of(client, case, row["T"])
    org = ig.org_state(client, case)
    active = ig.candidate_backups(client, case, row["T"])
    lines = []
    if g.status == guardians.COMPUTED:
        lines.append(f"Guardians as of {row['T_iso']}: {g.guardians} (provisional).")
    else:
        lines.append(f"Guardians as of {row['T_iso']}: {g.status}. {g.reason}")
    if keepers:
        lines.append(
            f"Recorded holders of release rights: {len(keepers)} "
            f"({', '.join(_short(k) for k in keepers)}, hashed)."
        )
    else:
        lines.append("Recorded holders of release rights: none in the graph (no grant records).")
    lines.append(
        f"Backup you named: {_short(org['backup'])} (hashed)."
        if org["backup"]
        else "Backup you named: none."
    )
    if active:
        lines.append(
            "Most active in the graph up to then, who you could name as a backup "
            f"(hashed): {', '.join(_short(a) for a in active[:5])}."
        )
    return Answer("guardians", "\n".join(lines), queries=list(g.queries), ms=g.query_ms or 0.0)


def _normal(client: FalkorClient, case: Case, row: dict) -> Answer:
    start = time.perf_counter()
    r = run_as_of(
        client,
        case.graph,
        "MATCH (n:Normal) WHERE n.computed_at <= $T "
        "RETURN n.metric, n.value, n.window, n.computed_at ORDER BY n.computed_at LIMIT 1000",
        {"T": row["T"]},
        timeout_ms=READ_MS,
    )
    ms = (time.perf_counter() - start) * 1000
    latest = {}
    for metric, value, window, at in r.result_set:
        latest[metric] = (value, window, at)
    if not latest:
        return Answer("normal", "No remembered normal is stored for this graph as of then.", ms=ms)
    parts = [f"{m} = {v} (window {w})" for m, (v, w, _at) in sorted(latest.items())]
    return Answer(
        "normal",
        f"Remembered normal as of {row['T_iso']}: " + "; ".join(parts) + ".",
        queries=[{"name": "normal_as_of", "ms": round(ms, 2), "rows": len(r.result_set)}],
        ms=ms,
    )


def _reviewed(client: FalkorClient, case: Case, row: dict) -> Answer:
    start = time.perf_counter()
    r = run_as_of(
        client,
        case.graph,
        "MATCH (a:Actor)-[:DID]->(x:Action {kind: 'review'}) "
        "WHERE x.at <= $T AND x.at > $start RETURN count(DISTINCT a), count(x) LIMIT 1",
        {"T": row["T"], "start": row["T"] - REVIEW_WINDOW_DAYS * DAY_S},
        timeout_ms=READ_MS,
    )
    ms = (time.perf_counter() - start) * 1000
    people, reviews = r.result_set[0]
    if not reviews:
        text = (
            f"No review records in the {REVIEW_WINDOW_DAYS} days up to {row['T_iso']}. "
            "This graph may not carry review events at all, so this is not evidence either way."
        )
    else:
        text = (
            f"{reviews} review records from {people} distinct people in the "
            f"{REVIEW_WINDOW_DAYS} days up to {row['T_iso']}."
        )
    return Answer(
        "who_reviewed",
        text,
        queries=[{"name": "reviews_as_of", "ms": round(ms, 2), "rows": 1}],
        ms=ms,
    )


def _history(results: Path) -> Answer:
    """Has this happened before? Counts from the saved decision files only."""
    lines, links = [], []
    for c in CASES.values():
        if not (results / c.decision_file).exists():
            continue
        rows = normalize_rows(c, results)
        fired = [r["quarter"] for r in rows if any(s == "FIRED" for s in r["moves"].values())]
        unknown = [r for r in rows if any(s == "NOT_COMPUTED" for s in r["moves"].values())]
        lines.append(
            f"{c.id} ({c.kind_word}): {len(rows)} quarters saved, a move fired in {len(fired)}, "
            f"{len(unknown)} had at least one move not computed."
        )
        links.append(_file_link(c.decision_file))
    gaps = results / "ecosystem_gaps.json"
    if gaps.exists():
        g = read_json(gaps)
        lines.append(
            f"The public xz record shows {g['gap_rows']} visibility-gap rows across "
            f"{g['decisions_computed']} downstream decisions (a lower bound)."
        )
        links.append(_file_link("ecosystem_gaps.json"))
    if not lines:
        lines.append("No saved results to compare with.")
    lines.append("Saved results only; nothing was re-run.")
    return Answer("history", "\n".join(lines), links=links)


def answer(client: FalkorClient, case: Case, row: dict, question: str, results: Path) -> Answer:
    tool = route(question)
    start = time.perf_counter()
    if tool == "refuse":
        ans = _refuse(case, row, results, question)
    elif tool == "takeover_cost":
        ans = _takeover(client, case, row)
    elif tool == "guardians":
        ans = _guardians(client, case, row)
    elif tool == "normal":
        ans = _normal(client, case, row)
    elif tool == "who_reviewed":
        ans = _reviewed(client, case, row)
    elif tool == "history":
        ans = _history(results)
    else:
        ans = Answer(
            "unsupported",
            "No tested tool covers that question, so I will not guess. I can answer: "
            + " ".join(SUPPORTED),
        )
    ans.ms = round((time.perf_counter() - start) * 1000, 2)
    ans.text += "\n(Answered by tested tools. No model was used.)"
    return ans
