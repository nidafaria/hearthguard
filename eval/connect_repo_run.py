"""One live run: connect a small public repo through the same job the UI starts, and time it.

Run: uv run python -m eval.connect_repo_run [owner/name]
Needs network (GitHub, read-only GETs) and FalkorDB. The token is read from .env if present
and is never printed or saved. Starts cold: the repo's raw cache and org graph are cleared
first, so the number is a first-connect time. Writes eval/results/connect_repo_run.json.
Nothing is claimed beyond the measured wall-clock.
"""

import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from packs.oss import connect_repo as C

REPO = "octocat/Hello-World"
RESULTS = Path(__file__).resolve().parent / "results"
POLL_S = 0.1


def main(argv: list[str]) -> int:
    repo = argv[0] if argv else REPO
    owner, name = C.parse_repo(repo)
    cache = C.RAW_ROOT / f"{owner}__{name}"
    graph = f"org_{C.graph_id(owner, name)}"

    cache_before = "present" if cache.exists() else "absent"
    if cache.exists():
        shutil.rmtree(cache)  # our own git-ignored cache for this repo; cleared so the run is cold
    FalkorClient().drop(graph)

    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    job_id = C.start_job(repo)
    while True:
        job = C.get_job(job_id)
        if job["state"] != "running":
            break
        time.sleep(POLL_S)
    wall = round(time.perf_counter() - t0, 3)

    result = job["result"]
    doc = {
        "repo": repo,
        "how": "start_job(repo), then get_job() polled until done: the UI connect path, "
        "without the browser",
        "cold_start": {"raw_cache_before": cache_before, "graph_dropped": graph},
        "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wall_clock_s": wall,
        "pipeline_wall_clock_s": result.get("wall_clock_s"),
        "job_state": job["state"],
        "status": result.get("status"),
        "reason": result.get("reason"),
        "requests": result.get("requests"),
        "counts": result.get("counts"),
        "metrics": result.get("metrics"),
        "takeover_cost": result.get("takeover_cost"),
        "guardians": result.get("guardians"),
        "best_hardening_step": result.get("best_hardening_step"),
        "steps": result.get("steps"),
        "label": C.LABEL,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "connect_repo_run.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    pipeline = result.get("wall_clock_s")
    print(f"{repo}: {result.get('status')} in {wall} s wall clock (pipeline {pipeline} s)")
    return 0 if result.get("status") == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
