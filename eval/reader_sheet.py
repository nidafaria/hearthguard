"""Read the Reader labelling sheet and check that a person has filled it in properly.

Only human labels count. A label cell must be "yes" or "no" (any capitalisation). Anything else,
including an empty cell, is reported by row and column, and the score is not computed.
"""

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from eval.reader_freeze import reader_kinds

RESULTS = Path(__file__).resolve().parent / "results"
SHEET_PATH = RESULTS / "reader_labelsheet.csv"
TESTSET_PATH = RESULTS / "reader_testset.json"

KINDS = reader_kinds()
COLUMNS = ["message_id", "year", "cleaned_text", *KINDS, "notes"]


def normalise(text: str) -> str:
    """Line endings and outer whitespace vary with the program that saved the sheet."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def read_sheet(path: Path | None = None) -> list[dict]:
    path = path or SHEET_PATH  # resolved at call time, so tests can point it elsewhere
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_label(cell: str | None) -> bool | None:
    """True for yes, False for no, None for anything else (including empty)."""
    value = (cell or "").strip().lower()
    return {"yes": True, "no": False}.get(value)


@dataclass
class LabelCheck:
    labels: dict[str, dict[str, bool]] = field(default_factory=dict)
    missing: list[tuple[str, list[str]]] = field(default_factory=list)  # (message id, kinds)
    invalid: list[tuple[str, str, str]] = field(default_factory=list)  # (id, kind, value)
    absent_ids: list[str] = field(default_factory=list)  # in the test set, not on the sheet
    unexpected_ids: list[str] = field(default_factory=list)  # on the sheet, not in the test set
    edited_text_ids: list[str] = field(default_factory=list)  # cleaned text no longer matches
    missing_columns: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not (
            self.missing
            or self.invalid
            or self.absent_ids
            or self.unexpected_ids
            or self.edited_text_ids
            or self.missing_columns
        )

    def describe(self) -> list[str]:
        lines = []
        if self.missing_columns:
            lines.append(f"columns missing from the sheet: {', '.join(self.missing_columns)}")
        for mid, kinds in self.missing:
            lines.append(f"{mid}: no label in {', '.join(kinds)}")
        for mid, kind, value in self.invalid:
            lines.append(f"{mid}: {kind} is {value!r}; it must be yes or no")
        if self.absent_ids:
            lines.append(f"not on the sheet: {', '.join(self.absent_ids)}")
        if self.unexpected_ids:
            lines.append(f"on the sheet but not in the test set: {', '.join(self.unexpected_ids)}")
        if self.edited_text_ids:
            lines.append(
                f"cleaned text was changed since the sheet was made: "
                f"{', '.join(self.edited_text_ids)}"
            )
        return lines


def check_labels(rows: list[dict], testset: dict) -> LabelCheck:
    """Compare the sheet with the test set: every row present, text unchanged, labels filled."""
    out = LabelCheck()
    wanted = {m["message_id"]: m for m in testset["messages"]}
    if rows:
        out.missing_columns = [c for c in COLUMNS if c not in rows[0]]
        if out.missing_columns:
            return out
    seen = set()
    for row in rows:
        mid = row["message_id"]
        seen.add(mid)
        if mid not in wanted:
            out.unexpected_ids.append(mid)
            continue
        if text_hash(row["cleaned_text"]) != wanted[mid]["text_sha256"]:
            out.edited_text_ids.append(mid)
        blanks, labels = [], {}
        for kind in KINDS:
            cell = (row.get(kind) or "").strip()
            parsed = parse_label(cell)
            if not cell:
                blanks.append(kind)
            elif parsed is None:
                out.invalid.append((mid, kind, cell))
            else:
                labels[kind] = parsed
        if blanks:
            out.missing.append((mid, blanks))
        if len(labels) == len(KINDS):
            out.labels[mid] = labels
    out.absent_ids = sorted(set(wanted) - seen)
    return out
