"""Weekly digest (spec 12.2): the product people see when nothing is wrong, and honest when
something is held. Built from saved result files only. No query runs, no model is called.

Pure core: digest_for_row(). build_digest() reads the saved files and picks the latest quarter.
A quiet week is one where no move fired, no move is unknown, Lone keeper is not set and the
decision is NO_ACTION.
"""

from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents.cases import MOVES, Case, normalize_rows, read_json


def _cell_text(cell: dict | None) -> str:
    if not cell:
        return "NOT COMPUTED"
    value = cell.get("value")
    if cell.get("status") == "COMPUTED" and value is not None:
        return str(value)
    return "NOT COMPUTED"


def normal_value(results: Path, case: Case, quarter: str, metric: str):
    name = "xz_normal.json" if case.id == "xz" else f"{case.id}_normal.json"
    path = results / name
    if not path.exists():
        return None
    for q in read_json(path)["results"]:
        if q["quarter"] == quarter:
            for m in q["metrics"]:
                if m["metric"] == metric and m["status"] == "COMPUTED":
                    return m["value"]
    return None


def digest_for_row(
    case: Case, row: dict, cells: dict[str, dict], active_keepers: float | int | None
) -> dict:
    fired = [m for m in MOVES if row["moves"][m] == "FIRED"]
    unknown = [m for m in MOVES if row["moves"][m] == "NOT_COMPUTED"]
    if row["lone_keeper"] == "FIRED":
        fired.append("LONE_KEEPER")
    lone_unknown = row["lone_keeper"] == "NOT_COMPUTED"
    quiet = not fired and not unknown and not lone_unknown and row["decision"] == "NO_ACTION"
    cost = _cell_text(cells.get("takeover_cost"))
    parts = [f"Takeover cost {cost}"]
    if quiet:
        parts.append("no open moves")
    else:
        parts.append(f"{len(fired)} moves fired" if fired else "no move fired")
        if unknown or lone_unknown:
            names = [*unknown, *(["LONE_KEEPER"] if lone_unknown else [])]
            parts.append(f"{len(names)} not checked ({', '.join(names)})")
    if active_keepers is not None:
        parts.append(f"{active_keepers} active keepers in the saved normal")
    headline = " · ".join(parts)
    if quiet:
        body = "Quiet week. Nothing needs your attention, and no note was raised."
    elif row["decision"] == "HOLD":
        body = (
            "Held, not clear: the unknown moves were not checked. "
            f"{row.get('hold_reason') or ''}".strip()
        )
    else:
        body = "A note is waiting in the inbox."
    return {
        "case": case.id,
        "label": case.label,
        "quarter": row["quarter"],
        "as_of": row["T_iso"],
        "quiet": quiet,
        "decision": row["decision"],
        "fired": fired,
        "unknown": [*unknown, *(["LONE_KEEPER"] if lone_unknown else [])],
        "takeover_cost": cost,
        "headline": headline,
        "text": f"{headline}\n{body}",
        "source": "saved results only; nothing was re-run",
    }


def build_digest(case: Case, results: Path) -> dict:
    rows = normalize_rows(case, results)
    row = max(rows, key=lambda r: r["T"])
    cells = ig.status_cells(case, results, row["quarter"])
    return digest_for_row(
        case, row, cells, normal_value(results, case, row["quarter"], "active_keepers")
    )
