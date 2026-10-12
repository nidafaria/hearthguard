"""Simulate a fix, live (spec 8.5, 12.2): up to three menu steps, each run on a GRAPH.COPY of the
org graph by core/hardening/ (simulate.py does the copy, the step and the measurement).

Takeover cost and guardians are measured before and after on every call. Caught and lead time
come only from a saved red-team result file. If none exists on disk they are NOT COMPUTED. The
org graph is never written to by a step; counts before and after are returned so that can be
checked. One Hardening node per step records the run.
"""

import json
import time
import uuid
from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents.cases import Case
from core.graph.client import FalkorClient
from core.hardening import simulate as sim
from core.hardening.xz import harden_org

MAX_STEPS = 3
RED_TEAM_GLOBS = ("redteam*.json", "hardening_redteam*.json")
NOT_COMPUTED = {"status": "NOT COMPUTED", "before": None, "after": None}
STEP_TEXT = {
    sim.STEP_ADD_KEEPER: "Add a second keeper with release rights",
    sim.STEP_PROVENANCE: "Require CI and provenance on release paths",
    sim.STEP_TWO_APPROVALS: "Require two approvals for every grant route",
}


def find_red_team(results: Path) -> tuple[str | None, dict[str, dict]]:
    """The saved red-team file and its per-step caught and lead-time values, if one exists.

    Expected shape (the keys of the Hardening node, spec 6.1):
    {"results": [{"step": ..., "caught_before": ..., "caught_after": ..., "lead_before": ...,
    "lead_after": ...}]}. Any other shape is not used and the values stay NOT COMPUTED.
    """
    for pattern in RED_TEAM_GLOBS:
        for path in sorted(results.glob(pattern)):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                steps = {r["step"]: r for r in doc["results"] if "step" in r}
            except (ValueError, KeyError, TypeError):
                continue
            return path.name, steps
    return None, {}


def _pair(src: dict | None, a: str, b: str) -> dict:
    if not src or src.get(a) is None or src.get(b) is None:
        return dict(NOT_COMPUTED)
    return {"status": "SAVED", "before": src[a], "after": src[b]}


def simulate_steps(
    client: FalkorClient,
    case: Case,
    row: dict,
    results: Path,
    steps: tuple[str, ...] = sim.MENU,
) -> dict:
    if len(steps) > MAX_STEPS:
        raise ValueError(f"at most {MAX_STEPS} steps, got {len(steps)}")
    for s in steps:
        if s not in sim.MENU:
            raise ValueError(f"unknown step {s!r}; menu is {sim.MENU}")
    red_file, red = find_red_team(results)
    graph = case.graph
    counts_before = sim.counts(client, graph)
    out = []
    start = time.perf_counter()
    for step in steps:
        t0 = time.perf_counter()
        # Graph names derive from the case's org, so a scratch org's copies carry its id.
        res = harden_org(client, case.org, step, row["T"], run=f"{case.org}_{uuid.uuid4().hex[:8]}")
        res["label"] = STEP_TEXT[step]
        res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        res["caught"] = _pair(red.get(step), "caught_before", "caught_after")
        res["lead_time"] = _pair(red.get(step), "lead_before", "lead_after")
        out.append(res)
    counts_after = sim.counts(client, graph)
    run_ref = f"live:{case.id}:{row['quarter']}"
    for res in out:
        ig.write_hardening(client, case, row["quarter"], res, run_ref)
    return {
        "steps": out,
        "T": row["T"],
        "T_iso": row["T_iso"],
        "total_ms": round((time.perf_counter() - start) * 1000, 1),
        "org_counts_before": counts_before,
        "org_counts_after": counts_after,
        "org_unchanged": counts_before == counts_after,
        "red_team_file": red_file,
        "red_team_note": (
            f"caught and lead time read from {red_file}"
            if red_file
            else "no saved red-team result file: caught and lead time are NOT COMPUTED"
        ),
        "provisional": True,
        "rule": "docs/decisions/0001-outsider-edges.md (PROPOSED, provisional)",
    }
