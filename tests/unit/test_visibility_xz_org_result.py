"""Row 35: the saved xz visibility run that includes the git commits (spec §6.1)."""

import json
from pathlib import Path

import pytest

from eval import populate_visibility as pv

RESULT = Path(__file__).resolve().parents[2] / "eval" / "results" / "visibility_xz_org.json"


@pytest.fixture(scope="module")
def saved() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_commits_and_mail_are_both_linked_to_a_place(saved):
    # Every message and every commit read has one RECORDED_IN edge.
    assert saved["git_commits_read"] > 0
    assert saved["counts_after_first_run"]["recorded_in"] == (
        saved["mail_messages_read"] + saved["git_commits_read"]
    )
    assert saved["counts_after_first_run"]["places"] == 2


def test_second_run_changes_no_count(saved):
    assert saved["idempotent"] is True
    assert saved["counts_after_first_run"] == saved["counts_after_second_run"]


def test_written_to_a_copy_never_to_the_source_graph(saved):
    assert saved["copied_from"] == "org_xz"
    assert saved["graph"] != saved["copied_from"]


def test_saved_file_holds_counts_only(saved):
    text = RESULT.read_text(encoding="utf-8")
    assert "@" not in text


def test_the_source_graph_is_refused_as_the_target():
    with pytest.raises(SystemExit):
        pv.main(["--graph", "org_xz", "--from-graph", "org_xz", "--out", "unused.json"])
