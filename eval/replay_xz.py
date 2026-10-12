"""Replay of the xz timeline, one row per quarter-end, built only from saved result files.

Run: python -m eval.replay_xz        (or: make replay CASE=xz)
Reads, and nothing else (no graph, no model, no network, no key):
  eval/results/xz_normal.json              normal metrics
  eval/results/xz_quarterly_status.json    Rush, Bypass, Lone keeper, takeover cost, guardians
  eval/results/pressure_vouch_status.json  Pressure, Vouch
  eval/results/decision_status.json        the decision
Writes eval/results/xz_replay.json and eval/results/xz_replay.md. Every cell is copied from one of
those files and the JSON names the file for each. No cell is typed by hand. The output has no
timestamp, so two runs over the same inputs give identical bytes.
"""

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
SOURCES = {
    "normal": "xz_normal.json",
    "quarterly": "xz_quarterly_status.json",
    "pv": "pressure_vouch_status.json",
    "decision": "decision_status.json",
}
OUT_JSON = RESULTS / "xz_replay.json"
OUT_MD = RESULTS / "xz_replay.md"
METRICS = ("cadence_days", "active_keepers", "usual_path")


def norm(status: str) -> str:
    return "NOT COMPUTED" if status in ("NOT COMPUTED", "NOT_COMPUTED") else status


def load(key: str, root: Path) -> dict:
    return json.loads((root / SOURCES[key]).read_text(encoding="utf-8"))


def missing(root: Path) -> list[str]:
    return [name for name in SOURCES.values() if not (root / name).exists()]


def build(root: Path = RESULTS) -> dict:
    normal = {r["quarter"]: r for r in load("normal", root)["results"]}
    quarterly = {r["quarter"]: r for r in load("quarterly", root)["quarters"]}
    pv_doc = load("pv", root)
    pv = {r["quarter"]: r for r in pv_doc["quarters"]}
    decision = {r["quarter"]: r for r in load("decision", root)["quarters"]}
    rows = []
    for quarter in sorted(decision):
        metrics = {}
        for m in normal[quarter]["metrics"]:
            if m["metric"] in METRICS:
                ok = m["status"] == "COMPUTED"
                metrics[m["metric"]] = {
                    "status": norm(m["status"]),
                    "value": m["value"] if ok else None,
                    "unit": m["unit"] if ok else None,
                    "n": m["n"] if ok else None,
                    "source": SOURCES["normal"],
                }
        checks = {
            name: {
                "status": norm(c["status"]),
                "reason": c["reason"],
                "source": SOURCES["quarterly"],
            }
            for name, c in quarterly[quarter]["checks"].items()
        }
        for name in ("pressure", "vouch"):
            checks[name] = {
                "status": norm(pv[quarter][name]["status"]),
                "reason": pv[quarter][name]["reason"],
                "source": SOURCES["pv"],
            }
        dec = decision[quarter]
        rows.append(
            {
                "quarter": quarter,
                "T_iso": dec["T_iso"],
                "normal": metrics,
                "checks": checks,
                "reader_unread_in_pressure_window": pv[quarter]["window_coverage"]["pressure"][
                    "unread"
                ],
                "decision": {
                    "type": dec["decision"],
                    "reason": dec["detail"].get("reason"),
                    "source": SOURCES["decision"],
                },
            }
        )
    return {
        "case": "xz",
        "what": "Replay of the public xz git history and xz-devel mailing list. Provisional.",
        "sources": list(SOURCES.values()),
        "reader_coverage": pv_doc["coverage"],
        "quarters": rows,
    }


def short(check: dict) -> str:
    return check["status"]


def table(doc: dict) -> str:
    cols = ["quarter", "cadence_days", "active_keepers", "rush", "bypass", "lone_keeper"]
    cols += ["takeover_cost", "guardians", "pressure", "vouch", "unread_120d", "decision"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in doc["quarters"]:
        cadence = r["normal"].get("cadence_days", {})
        keepers = r["normal"].get("active_keepers", {})
        cells = [
            r["quarter"],
            "NOT COMPUTED" if cadence.get("value") is None else f"{cadence['value']:.4f}",
            "NOT COMPUTED" if keepers.get("value") is None else str(keepers["value"]),
        ]
        cells += [short(r["checks"][c]) for c in cols[3:-2]]
        cells.append(str(r["reader_unread_in_pressure_window"]))
        cells.append(r["decision"]["type"])
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def markdown(doc: dict) -> str:
    cov = doc["reader_coverage"]
    return "\n".join(
        [
            "# xz replay (provisional)",
            "",
            doc["what"],
            "",
            f"Reader coverage: {cov['read_so_far']} of {cov['to_read']} messages read "
            f"({'complete' if cov['complete'] else 'INCOMPLETE'}); "
            f"{cov['excluded_human_labelled_test_set']} messages are held back for the "
            "human-labelled test set.",
            "",
            table(doc),
            "",
            "Sources: " + ", ".join(doc["sources"]) + ". Every cell is copied from one of them.",
            "unread_120d is the number of in-scope messages in the Pressure window the Reader has "
            "not read; a NOT_FIRED with unread messages is a result on the messages read only.",
            "NOT COMPUTED means the input does not exist in the public data; it is not a clean "
            "result.",
            "",
        ]
    )


def main() -> int:
    gone = missing(RESULTS)
    if gone:
        print("Cannot replay; missing result files:", ", ".join(gone))
        return 1
    doc = build()
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    text = markdown(doc)
    OUT_MD.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
