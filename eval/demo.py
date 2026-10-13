"""The demo: the xz replay, then gaps, hardening and tallowdate summaries, from saved results only.

Run: python -m eval.demo        (or: make demo)
No network, no key, no graph, no model. It reads the result files named in eval/replay_xz.py and
in the sections below. It writes nothing and prints no time, so every run on the same files prints
the same bytes. A section whose file is missing says NOT COMPUTED and names the file; nothing is
invented in its place.
"""

import json
from pathlib import Path

from eval import gaps_report, replay_xz

NOT_COMPUTED = "NOT COMPUTED"
SYNTHETIC = "SYNTHETIC: fictional project, fictional people. Not a finding."


def _load(name: str, results: Path | None = None) -> dict | None:
    # Read replay_xz.RESULTS at call time, so a caller (or a test) can point it elsewhere.
    path = (results or replay_xz.RESULTS) / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _missing(name: str) -> str:
    return f"{NOT_COMPUTED}: {name} not found. Build it first (see README, Commands)."


def _cost(cell: dict) -> str:
    if cell.get("status") == "COMPUTED":
        return str(cell.get("value"))
    return NOT_COMPUTED


def gaps_section(results: Path | None = None) -> str:
    doc = _load("ecosystem_gaps.json", results)
    if doc is None:
        return _missing("ecosystem_gaps.json")
    return gaps_report.markdown(doc)


def hardening_section(results: Path | None = None) -> str:
    out = ["## Hardening, from saved results", ""]
    xz = _load("xz_hardening.json", results)
    if xz is None:
        out.append(_missing("xz_hardening.json"))
    else:
        steps = [(q["quarter"], s) for q in xz["results"] for s in q["steps"]]
        applied = sum(1 for _, s in steps if s["applied"])
        before = sorted({_cost(s["before"]["takeover_cost"]) for _, s in steps})
        after = sorted({_cost(s["after"]["takeover_cost"]) for _, s in steps})
        out.append(
            f"org xz: {len(xz['results'])} quarter-ends, {len(steps)} steps, {applied} applied. "
            f"Takeover cost before: {', '.join(before)}. After: {', '.join(after)}. "
            "Caught and lead time: not in this file."
        )
    fixture = _load("hardening_fixture.json", results)
    out.append("")
    if fixture is None:
        out.append(_missing("hardening_fixture.json"))
    else:
        out += [
            "| Fixture | Step | Cost before | Cost after | Guardians before | Guardians after |",
            "|---|---|---|---|---|---|",
        ]
        for r in fixture["results"]:
            out.append(
                f"| {r['fixture']} | {r['step']} | {r['before']['cost']} | {r['after']['cost']} | "
                f"{r['before']['guardians']} | {r['after']['guardians']} |"
            )
    return "\n".join(out)


def tallowdate_section(results: Path | None = None) -> str:
    out = ["## tallowdate, synthetic case", "", SYNTHETIC, ""]
    dec = _load("tallowdate_decision.json", results)
    det = _load("tallowdate_detector_status.json", results)
    if dec is None:
        out.append(_missing("tallowdate_decision.json"))
    else:
        out += ["| Quarter | Decision | Reason |", "|---|---|---|"]
        for q in dec["quarters"]:
            out.append(f"| {q['quarter']} | {q['decision']} | {q.get('hold_reason') or ''} |")
    out.append("")
    if det is None:
        out.append(_missing("tallowdate_detector_status.json"))
    else:
        out += ["| Quarter | Takeover cost | Guardians |", "|---|---|---|"]
        for q in det["quarters"]:
            out.append(
                f"| {q['quarter']} | {_cost(q['checks']['takeover_cost'])} | "
                f"{_cost(q['checks']['guardians'])} |"
            )
    return "\n".join(out)


def main() -> int:
    gone = replay_xz.missing(replay_xz.RESULTS)
    if gone:
        print("Cannot run the demo; missing result files:", ", ".join(gone))
        print("Build them first: see README.md, section 'Commands'.")
        return 1
    print(replay_xz.markdown(replay_xz.build()))
    print()
    print("## Visibility gaps, xz")
    print()
    print(gaps_section())
    print()
    print(hardening_section())
    print()
    print(tallowdate_section())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
