"""'Show me why' for one quarter: each fact, the saved file it came from, and the query behind it.

Reads saved results only. No query runs, no graph is touched, no model is called.
The status files are the ones decision_status.json names in its "inputs" field.
"""

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results"
PV_NAME = "pressure_vouch_status.json"
QS_NAME = "xz_quarterly_status.json"

# Fact order matches the note. Each entry: (label, source file, where to find it in that file).
FACTS = [
    ("PRESSURE", PV_NAME, ("pressure",)),
    ("VOUCH", PV_NAME, ("vouch",)),
    ("RUSH", QS_NAME, ("checks", "rush")),
    ("BYPASS", QS_NAME, ("checks", "bypass")),
    ("LONE_KEEPER", QS_NAME, ("checks", "lone_keeper")),
]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(status: str) -> str:
    return status.replace("NOT COMPUTED", "NOT_COMPUTED")


def facts_for(decision_row: dict, results: Path = RESULTS) -> list[dict]:
    """Each fact for one decision row, with the file and the queries it came from.

    The status shown is the one the decision used. If the source file disagrees, this raises
    rather than showing two different answers.
    """
    quarter = decision_row["quarter"]
    sources = {
        PV_NAME: _index(_read(results / PV_NAME)),
        QS_NAME: _index(_read(results / QS_NAME)),
    }
    out = []
    for label, file_name, path in FACTS:
        node = sources[file_name][quarter]
        for key in path:
            node = node[key]
        status = _norm(node["status"])
        if label == "LONE_KEEPER":
            recorded_status = decision_row["lone_keeper"]
        else:
            recorded_status = decision_row["moves"][label]
        if recorded_status != status:
            raise ValueError(
                f"{quarter} {label}: decision says {recorded_status}, file says {status}"
            )
        out.append(
            {
                "fact": label,
                "status": status,
                "reason": node["reason"],
                "file": file_name,
                "queries": [
                    {
                        "name": q["name"],
                        "query": q["query"],
                        "rows": q["rows"],
                        "ms": q.get("ms") or 0,
                    }
                    for q in node.get("queries", [])
                ],
            }
        )
    return out


def _index(doc: dict) -> dict:
    return {q["quarter"]: q for q in doc["quarters"]}


def render_show_why(decision_row: dict, results: Path = RESULTS) -> str:
    """The thread reply: each fact with its file, its query, and the query time."""
    quarter = decision_row["quarter"]
    breakdown = decision_row.get("detail", {}).get("breakdown", {})
    lines = [
        f"Show me why: {quarter}, decision {decision_row['decision']}",
        f"Rule: {breakdown.get('rule', 'not recorded')}. Saved as of {decision_row['T_iso']}.",
        "",
    ]
    total_ms = 0.0
    for number, fact in enumerate(facts_for(decision_row, results), start=1):
        lines.append(f"{number}. {fact['fact'].replace('_', ' ').title()}: {fact['status']}")
        lines.append(f"   Reason: {fact['reason']}")
        lines.append(f"   File: {fact['file']}")
        if not fact["queries"]:
            lines.append("   Query: none recorded in the saved file")
        for q in fact["queries"]:
            total_ms += q["ms"]
            lines.append(f"   Query {q['name']} ({q['rows']} rows, {q['ms']:.1f} ms):")
            lines.append(f"     {q['query']}")
    lines.append("")
    lines.append(f"Total query time: {total_ms:.1f} ms. Saved results only; nothing was re-run.")
    return "\n".join(lines)
