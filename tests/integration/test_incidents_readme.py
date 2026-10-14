"""README checks (spec §1 R10, R11, R5): setup, graph model, queries, measured numbers, limits,
AI use and tracks are all there, and nothing it points to is missing.

Hand-worked expectations:
  - the README has a section for each of: setup, commands, graph data model, queries and
    algorithms, what is measured, what is NOT COMPUTED, limitations, AI disclosure, tracks;
  - every `uv run python -m <module>` it shows names a module that exists;
  - every repo path it cites (eval/results/..., docs/..., core/..., packs/...) exists, except the
    files the lead writes on main after the merge (EXEMPT);
  - Track 02 is named; the demo video is said to be absent rather than linked.
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
EXEMPT = {"eval/results/makefile_gaps.md"}  # written on main after this block merges

SECTIONS = (
    "## Setup",
    "## Commands",
    "## Graph data model",
    "## Queries and algorithms the product depends on",
    "## What is measured",
    "## What is NOT COMPUTED, and why",
    "## Limitations",
    "## AI disclosure",
    "## Tracks",
)


def test_every_required_section_is_present():
    for s in SECTIONS:
        assert s in README, s


def test_every_module_in_a_command_exists():
    mods = set(re.findall(r"uv run python -m ([\w.]+)", README))
    assert mods
    for m in mods:
        assert importlib.util.find_spec(m) is not None, m


def test_every_cited_path_exists():
    paths = set(
        re.findall(r"\b((?:eval/results|docs|core|packs|api)/[\w./<>*-]+\.(?:json|md|py))", README)
    )
    missing = [
        p
        for p in sorted(paths)
        if "<" not in p and "*" not in p and p not in EXEMPT and not (ROOT / p).exists()
    ]
    assert missing == []


def test_track_and_video_are_stated_plainly():
    assert "Track 02" in README
    assert "not recorded yet" in README
    assert "does **not** detect the xz backdoor" in README


def test_the_incident_commands_are_documented():
    for m in (
        "eval.incidents_fetch",
        "eval.incidents_load",
        "eval.replay_event_stream",
        "eval.replay_axios",
    ):
        assert f"uv run python -m {m}" in README, m
