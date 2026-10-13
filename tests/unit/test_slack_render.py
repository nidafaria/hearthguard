"""The Slack note and "Show me why" text, rendered from saved results. No Slack, no network."""

import json
import re

import pytest

from slack_app.render import DECISION, OUT, build_preview, render_note
from slack_app.show_why import RESULTS, facts_for, render_show_why

FORBIDDEN_PHRASES = ["attacker", "is compromised"]
# Personal names that must never appear in a note. "Jia Tan" is the one allowed name (a public,
# adjudicated case). This is a denylist: it catches the names we know about, not every name.
DENIED_NAMES = ["Lasse", "Collin", "Tomás", "Tomas", "Rowan", "Dennis", "Sam "]


@pytest.fixture(scope="module")
def decision_doc():
    return json.loads(DECISION.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(decision_doc):
    return decision_doc["quarters"]


def _all_text(row):
    return render_note(row) + "\n" + render_show_why(row)


def test_no_note_or_show_why_uses_forbidden_phrases(rows):
    for row in rows:
        text = _all_text(row).lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"{row['quarter']} contains {phrase!r}"


def test_no_note_names_a_person_except_jia_tan(rows):
    for row in rows:
        text = _all_text(row)
        for name in DENIED_NAMES:
            assert name not in text, f"{row['quarter']} contains {name!r}"


def test_every_hold_renders_as_held_not_no_concern(rows):
    holds = [r for r in rows if r["decision"] == "HOLD"]
    assert holds, "expected at least one HOLD in decision_status.json"
    for row in holds:
        note = render_note(row)
        assert note.startswith("**Held: "), row["quarter"]
        assert "no concern" not in note.lower(), row["quarter"]
        assert "no concern" not in render_show_why(row).lower(), row["quarter"]


def test_every_note_ends_with_a_question(rows):
    for row in rows:
        question_lines = [ln for ln in render_note(row).splitlines() if ln.endswith("?")]
        assert question_lines, f"{row['quarter']} has no question"
        assert question_lines[0].startswith("Would you like"), row["quarter"]


def test_unknown_moves_are_named_in_the_note(rows):
    for row in rows:
        note = render_note(row)
        for move in row["detail"]["breakdown"]["unknown_moves"]:
            assert f"**{move.title()}**: unknown, not checked" in note, row["quarter"]
        assert "not that they are clear" in note or not row["detail"]["breakdown"]["unknown_moves"]


def test_show_why_lists_each_fact_with_file_and_query(rows):
    for row in rows:
        facts = facts_for(row)
        assert [f["fact"] for f in facts] == ["PRESSURE", "VOUCH", "RUSH", "BYPASS", "LONE_KEEPER"]
        text = render_show_why(row)
        for fact in facts:
            assert fact["file"] in text, (row["quarter"], fact["fact"])
            assert fact["queries"], (row["quarter"], fact["fact"], "no query recorded")
            for q in fact["queries"]:
                assert q["query"] in text, (row["quarter"], q["name"])


def test_show_why_status_matches_the_decision(rows):
    for row in rows:
        for fact in facts_for(row):
            if fact["fact"] == "LONE_KEEPER":
                assert fact["status"] == row["lone_keeper"]
            else:
                assert fact["status"] == row["moves"][fact["fact"]]


GENERATED = "decision_status_generated_at_utc"


def test_preview_file_matches_a_fresh_render(decision_doc):
    # decision-xz rewrites only the generated_at_utc stamp of decision_status.json on every run, so
    # the stamp is compared as a timestamp and the content is compared without it.
    assert OUT.exists(), "run: make slack-preview"
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    fresh = build_preview(decision_doc)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", saved.pop(GENERATED))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", fresh.pop(GENERATED))
    assert saved == fresh
    assert saved["sent_to_slack"] is False


def test_preview_covers_every_quarter_in_order(decision_doc):
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    assert [q["quarter"] for q in saved["quarters"]] == [
        r["quarter"] for r in decision_doc["quarters"]
    ]


def test_results_directory_is_the_saved_one():
    assert (RESULTS / "decision_status.json").exists()
