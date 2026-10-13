"""`make gaps CASE=xz`: print the visibility gaps from the saved ecosystem_xz output.

Reads eval/results/ecosystem_gaps.json, written by `make ecosystem-xz` (eval/ecosystem_xz.py), and
writes the same gaps as Markdown to eval/results/gaps_xz.md. It runs no query, makes no network call
and needs no FalkorDB. Roles are printed, never names: the saved events carry persona fields and
none of them is read here.

Run: python -m eval.gaps_report xz     (or: make gaps CASE=xz)
"""

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
CASES = {"xz": "ecosystem_gaps.json"}


def markdown(doc: dict) -> str:
    lines = [
        "# Visibility gaps, " + doc["graph"],
        "",
        doc["scope"],
        "",
        f"Decisions computed: {doc['decisions_computed']}, "
        f"not computed: {doc['decisions_not_computed']}. "
        f"Gap rows: {doc['gap_rows']} ({doc['unreachable_rows']} UNREACHABLE, "
        f"{doc['unnoticed_rows']} UNNOTICED). Label confidence: "
        + ", ".join(f"{k} {v}" for k, v in sorted(doc["label_confidence_counts"].items()))
        + ".",
        "",
        "| Decision | Place | Deciding role | Status | Gap | Signal | Signal at (UTC) | Label |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in doc["decisions"]:
        if d["status"] != "COMPUTED":
            lines.append(
                f"| {d['decision']} | {d['place']} | {d['deciding_role']} | NOT COMPUTED | "
                f"{d.get('reason') or ''} | | | |"
            )
            continue
        if not d["gaps"]:
            lines.append(
                f"| {d['decision']} | {d['place']} | {d['deciding_role']} | COMPUTED | none | | | |"
            )
        for g in d["gaps"]:
            lines.append(
                f"| {d['decision']} | {d['place']} | {d['deciding_role']} | COMPUTED | "
                f"{g['gap']} | "
                f"{g['signal_kind']} in {g['signal_place']} | {g['signal_at']} | "
                f"{g['label_confidence']} |"
            )
    lines += ["", "Reading the labels: " + doc["reading_the_labels"], ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    case = argv[0] if argv else "xz"
    if case not in CASES:
        print(f"no gaps for CASE={case}; known: {', '.join(CASES)}")
        return 2
    path = RESULTS / CASES[case]
    if not path.exists():
        print(f"missing {path.name}: run `make ecosystem-xz` first (needs network)")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    text = markdown(doc)
    (RESULTS / f"gaps_{case}.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
