"""No note contains an accusation. A note is a question to the person in charge, nothing more."""

import copy
import json

import pytest

from slack_app.render import DECISION, OUT, render_note
from slack_app.rules import ends_with_question, find_accusations
from slack_app.show_why import render_show_why

ACCUSING = [
    "This account is an attacker.",
    "The maintainer is compromised.",
    "Account X is compromised by the look of it.",
    "He planted the change.",
    "They did it on purpose.",
    "You stole the release key.",
    "She is a liar.",
    "This is a malicious account.",
    "It was a threat actor.",
    "The contributor is the culprit.",
    "THEY ARE GUILTY.",
]

NOT_ACCUSING = [
    "Would you like to review who can publish?",
    "Held: 2021-Q4. Unknown: RUSH, BYPASS.",
    "This is not a judgement about anyone.",
    "Rush: unknown, not checked (no Privilege of kind 'release' in org_xz).",
    "Lone keeper: did not fire.",
    "Would you like to keep watching this project?",
]


@pytest.mark.parametrize("text", ACCUSING)
def test_rule_catches_accusing_wording(text):
    assert find_accusations(text), text


@pytest.mark.parametrize("text", NOT_ACCUSING)
def test_rule_passes_question_and_status_wording(text):
    assert find_accusations(text) == [], text


def test_question_rule():
    assert ends_with_question("Held.\nWould you like to review who can publish?")
    assert not ends_with_question("Held. No question here.")


@pytest.fixture(scope="module")
def decision_rows():
    return json.loads(DECISION.read_text(encoding="utf-8"))["quarters"]


def test_every_rendered_note_is_a_question_with_no_accusation(decision_rows):
    for row in decision_rows:
        note = render_note(row)
        assert find_accusations(note) == [], row["quarter"]
        assert ends_with_question(note), row["quarter"]


def test_every_show_why_text_has_no_accusation(decision_rows):
    for row in decision_rows:
        assert find_accusations(render_show_why(row)) == [], row["quarter"]


def test_saved_preview_has_no_accusation():
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    for q in saved["quarters"]:
        assert find_accusations(q["note"]) == [], q["quarter"]
        assert find_accusations(q["show_why"]) == [], q["quarter"]


def test_renderer_refuses_an_accusing_reason(decision_rows):
    row = copy.deepcopy(decision_rows[0])
    row["detail"]["reason"] = "the maintainer is an attacker"
    with pytest.raises(ValueError, match="accusing wording"):
        render_note(row)
