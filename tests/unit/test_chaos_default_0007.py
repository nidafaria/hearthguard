"""Row 80: under the default in docs/decisions/0007 (2026-10-18), "a different exception" means a
different pattern. Reads the saved chaos files only; nothing is rerun and nothing is invented."""

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"


def saved_seeds() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(RESULTS.glob("learning_chaos_seed*.json"))
    ]


def test_saved_seeds_cover_three_patterns():
    assert len({s["pattern"] for s in saved_seeds()}) >= 3


def test_one_pattern_gives_one_exception_and_different_patterns_give_different_ones():
    by_pattern: dict[str, set[str]] = {}
    for s in saved_seeds():
        by_pattern.setdefault(s["pattern"], set()).add(s["exception_id"])
    assert all(len(ids) == 1 for ids in by_pattern.values())
    all_ids = [next(iter(ids)) for ids in by_pattern.values()]
    assert len(set(all_ids)) == len(all_ids)
