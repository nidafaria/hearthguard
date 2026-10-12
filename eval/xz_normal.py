"""Compute the remembered-normal metrics for xz at each quarter-end and export them as JSON.

Run: python -m eval.xz_normal
Writes eval/results/xz_normal.json. Every value carries the exact query that produced it, its
parameters, and the query time. A metric the data cannot support is NOT COMPUTED with a reason.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.normal import metrics
from packs.oss import git_ingest, xz_graph

OUT = Path(__file__).resolve().parent / "results" / "xz_normal.json"

# Every quarter-end from 2021-Q4 to 2024-Q1.
QUARTER_ENDS: tuple[tuple[str, date], ...] = (
    ("2021-Q4", date(2021, 12, 31)),
    ("2022-Q1", date(2022, 3, 31)),
    ("2022-Q2", date(2022, 6, 30)),
    ("2022-Q3", date(2022, 9, 30)),
    ("2022-Q4", date(2022, 12, 31)),
    ("2023-Q1", date(2023, 3, 31)),
    ("2023-Q2", date(2023, 6, 30)),
    ("2023-Q3", date(2023, 9, 30)),
    ("2023-Q4", date(2023, 12, 31)),
    ("2024-Q1", date(2024, 3, 31)),
)


def end_of_day_utc(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).timestamp())


def main() -> int:
    client = FalkorClient()
    org = xz_graph.ORG_ID
    fetch = json.loads((git_ingest.RAW_DIR / "xz.fetch.json").read_text(encoding="utf-8"))
    results = []
    for quarter, d in QUARTER_ENDS:
        T = end_of_day_utc(d)
        computed = [
            metrics.commit_cadence_days(client, org, T),
            metrics.active_keepers_as_of_T(client, org, T),
            metrics.release_channel_as_of_T(client, org, T),
        ]
        for res in computed:
            metrics.store(client, org, res)
        all_metrics = computed + [
            metrics.keeper_activity_median_90d(T),
            metrics.grant_days(T),
            metrics.trusted_actor_set(T),
        ]
        results.append(
            {
                "quarter": quarter,
                "T": T,
                "T_iso": datetime.fromtimestamp(T, UTC).isoformat().replace("+00:00", "Z"),
                "metrics": [m.as_dict() for m in all_metrics],
            }
        )
    doc = {
        "org": org,
        "graph": xz_graph.GRAPH,
        "source": {
            "url": fetch["source_url"],
            "head_sha": fetch["head_sha"],
            "fetched_at_utc": fetch["fetched_at_utc"],
        },
        "time_unit": "Unix epoch seconds, UTC. T is 23:59:59 UTC on the quarter-end date.",
        "notes": [
            "This is the public xz git history only. The xz backdoor was in release tarballs, "
            "not in the git history, so these numbers do not show the backdoor.",
            "active_keepers counts distinct commit AUTHORS, as specified. An author is not always "
            "someone with commit access (the committer may differ), so this can overcount keepers.",
            "usual_path for releases is always 'git' here because git is the only channel this "
            "ingest can see. Tarball and CI paths are not observable from git.",
            "cadence_days is the median gap between consecutive commits by author time, "
            "interpolated for an even count (percentileCont 0.5).",
            "computed_at on stored Normal nodes holds T, not the wall clock.",
        ],
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for r in results:
        line = " | ".join(
            f"{m['metric']}={m['value'] if m['status'] == metrics.COMPUTED else 'NOT COMPUTED'}"
            for m in r["metrics"][:3]
        )
        print(f"{r['quarter']} T={r['T']}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
