"""Remembered-normal metrics for org_tallowdate at each quarter-end, 2023-Q1 to 2025-Q4.

Run: uv run python -m redteam.tallowdate_normal
Writes eval/results/tallowdate_normal.json. Same metric functions as eval/xz_normal.py, called
unchanged. Every value carries its query, parameters and query time. A metric the data cannot
support is NOT COMPUTED with a reason. Synthetic case: every output carries synthetic: true.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.normal import metrics
from redteam.load_tallowdate import GRAPH, ORG_ID

OUT = Path(__file__).resolve().parent.parent / "eval" / "results" / "tallowdate_normal.json"

QUARTER_ENDS: tuple[tuple[str, date], ...] = (
    ("2023-Q1", date(2023, 3, 31)),
    ("2023-Q2", date(2023, 6, 30)),
    ("2023-Q3", date(2023, 9, 30)),
    ("2023-Q4", date(2023, 12, 31)),
    ("2024-Q1", date(2024, 3, 31)),
    ("2024-Q2", date(2024, 6, 30)),
    ("2024-Q3", date(2024, 9, 30)),
    ("2024-Q4", date(2024, 12, 31)),
    ("2025-Q1", date(2025, 3, 31)),
    ("2025-Q2", date(2025, 6, 30)),
    ("2025-Q3", date(2025, 9, 30)),
    ("2025-Q4", date(2025, 12, 31)),
)


def end_of_day_utc(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).timestamp())


def build(client: FalkorClient) -> dict:
    results = []
    for quarter, d in QUARTER_ENDS:
        T = end_of_day_utc(d)
        computed = [
            metrics.commit_cadence_days(client, ORG_ID, T),
            metrics.active_keepers_as_of_T(client, ORG_ID, T),
            metrics.release_channel_as_of_T(client, ORG_ID, T),
        ]
        for res in computed:
            metrics.store(client, ORG_ID, res)
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
    return {
        "synthetic": True,
        "case": "tallowdate",
        "org": ORG_ID,
        "graph": GRAPH,
        "source": {
            "url": "data/synthetic/tallowdate.json (generated, not fetched)",
            "generator": "redteam/tallowdate.py",
        },
        "time_unit": "Unix epoch seconds, UTC. T is 23:59:59 UTC on the quarter-end date.",
        "notes": [
            "SYNTHETIC case. Every number comes from the generated events, not from any project.",
            "The story events are in 2026, after the last quarter-end in this table (2025-Q4). "
            "Quarters from 2023-Q1 to 2025-Q4 hold only the generated background reviews, so "
            "the story is not inside any of these windows.",
            "Merged pull requests are recorded as commits (Action kind 'commit'). This is a "
            "mapping choice for the synthetic case, not a claim about real commit history.",
        ],
        "results": results,
    }


def main() -> int:
    doc = build(FalkorClient())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for r in doc["results"]:
        line = " | ".join(
            f"{m['metric']}={m['value'] if m['status'] == metrics.COMPUTED else 'NOT COMPUTED'}"
            for m in r["metrics"][:3]
        )
        print(f"{r['quarter']} T={r['T']}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
