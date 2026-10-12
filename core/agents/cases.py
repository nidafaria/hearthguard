"""The two cases the inbox can show, and their decision rows in one shape (spec 12.2, 4.5).

xz is the public record (org_xz). tallowdate is the synthetic demo (org_tallowdate). Every API
response and screen carries the label of its case. Rows come from saved result files only.
The two decision files differ a little; normalize_rows() gives both the same fields.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"
MOVES = ("PRESSURE", "VOUCH", "RUSH", "BYPASS")

XZ_LABEL = "Public record: xz project git history (org_xz). Synthetic data: none on this screen."
TALLOWDATE_LABEL = (
    "SYNTHETIC demo data: the fictional project tallowdate (org_tallowdate). "
    "Public record: none on this screen."
)


@dataclass(frozen=True)
class Case:
    id: str
    org: str  # the org id; the graph is org_<org>
    label: str
    synthetic: bool
    decision_file: str
    detail_files: tuple[str, ...]  # saved status files that hold each move's reason
    hardening_file: str | None  # saved hardening result (xz only)

    @property
    def graph(self) -> str:
        return f"org_{self.org}"

    @property
    def kind_word(self) -> str:
        return "synthetic" if self.synthetic else "public record"


CASES: dict[str, Case] = {
    "xz": Case(
        id="xz",
        org="xz",
        label=XZ_LABEL,
        synthetic=False,
        decision_file="decision_status.json",
        detail_files=("pressure_vouch_status.json", "xz_quarterly_status.json"),
        hardening_file="xz_hardening.json",
    ),
    "tallowdate": Case(
        id="tallowdate",
        org="tallowdate",
        label=TALLOWDATE_LABEL,
        synthetic=True,
        decision_file="tallowdate_decision.json",
        detail_files=("tallowdate_detector_status.json",),
        hardening_file=None,
    ),
}


def get_case(case_id: str) -> Case:
    try:
        return CASES[case_id]
    except KeyError:
        raise KeyError(f"no such case {case_id!r}; cases are {sorted(CASES)}") from None


def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _detail_reasons(case: Case, results: Path, quarter: str) -> dict[str, str]:
    """Each move's saved reason for one quarter, from the status files the decision names."""
    found: dict[str, str] = {}
    for name in case.detail_files:
        path = results / name
        if not path.exists():
            continue
        for q in read_json(path)["quarters"]:
            if q["quarter"] != quarter:
                continue
            if "checks" in q:
                for key, check in q["checks"].items():
                    found.setdefault(key.upper(), check.get("reason") or "")
            for key in ("pressure", "vouch"):
                if key in q:
                    found.setdefault(key.upper(), q[key].get("reason") or "")
    return found


def normalize_rows(case: Case, results: Path = RESULTS) -> list[dict]:
    """One dict per quarter with the same keys for every case.

    Keys: quarter, T, T_iso, decision, moves, lone_keeper, reasons, detail, hold_reason.
    A move's status is exactly what the decision file recorded. Nothing is filled in.
    """
    doc = read_json(results / case.decision_file)
    out = []
    for row in doc["quarters"]:
        T = row["T"] if "T" in row else epoch(row["T_iso"])
        reasons = dict(row.get("reasons") or {})
        if not reasons:
            saved = _detail_reasons(case, results, row["quarter"])
            reasons = {m: saved.get(m) or "reason not recorded" for m in MOVES}
        out.append(
            {
                "quarter": row["quarter"],
                "T": T,
                "T_iso": row.get("T_iso") or iso(T),
                "decision": row["decision"],
                "moves": dict(row["moves"]),
                "lone_keeper": row["lone_keeper"],
                "reasons": reasons,
                "detail": row["detail"],
                "hold_reason": row["detail"].get("reason"),
            }
        )
    return out


def row_for(case: Case, quarter: str, results: Path = RESULTS) -> dict | None:
    for r in normalize_rows(case, results):
        if r["quarter"] == quarter:
            return r
    return None
