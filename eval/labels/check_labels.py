"""Count filled labels in eval/labels/to_label.csv and flag bad ones.

Run: uv run python eval/labels/check_labels.py [path-to-csv]
Read-only. It never edits the file. Allowed labels are in eval/labels/README.md.
"""
import csv
import sys
from pathlib import Path

ALLOWED = {
    "NONE",
    "PRESSURE",
    "URGENCY",
    "VOUCH",
    "REQUESTS_PRIVILEGE",
    "CAPACITY_STATEMENT",
    "CHANGE_REQUEST",
    "HANDOVER_ANNOUNCEMENT",
}
EXPECTED_ROWS = 60


def parse(cell):
    """Split a label cell on ; or , into upper-case parts."""
    parts = cell.replace(",", ";").split(";")
    return [p.strip().upper() for p in parts if p.strip()]


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("to_label.csv")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    filled, empty, problems = 0, [], []
    seen = set()
    for r in rows:
        mid = r.get("id", "?")
        if mid in seen:
            problems.append(f"{mid}: id appears twice")
        seen.add(mid)
        parts = parse(r.get("label") or "")
        if not parts:
            empty.append(mid)
            continue
        filled += 1
        bad = [p for p in parts if p not in ALLOWED]
        if bad:
            problems.append(f"{mid}: not an allowed label: {', '.join(bad)}")
        if "NONE" in parts and len(parts) > 1:
            problems.append(f"{mid}: NONE cannot be mixed with other labels")
    print(f"rows: {len(rows)} (expected {EXPECTED_ROWS})")
    print(f"filled: {filled}")
    print(f"empty: {len(empty)}")
    if empty:
        print("  still to label: " + ", ".join(empty))
    print(f"bad: {len(problems)}")
    for p in problems:
        print("  " + p)
    if len(rows) != EXPECTED_ROWS:
        problems.append("wrong row count")
    return 0 if not empty and not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
