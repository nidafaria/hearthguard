"""The local inbox API. Runs on a temp copy of the saved results and a temp inbox file."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import LABEL, create_app
from slack_app.rules import ends_with_question, find_accusations
from slack_app.show_why import PV_NAME, QS_NAME, RESULTS

SRC_FILES = ["decision_status.json", PV_NAME, QS_NAME]


@pytest.fixture
def results(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    for name in SRC_FILES:
        shutil.copy(RESULTS / name, d / name)
    return d


@pytest.fixture
def inbox(tmp_path):
    return tmp_path / "inbox" / "dismissals.jsonl"


@pytest.fixture
def client(results, inbox):
    return TestClient(create_app(results=results, inbox_file=inbox))


def _quarters(client):
    return [n["quarter"] for n in client.get("/api/notes").json()["notes"]]


def test_health_says_nothing_is_sent(client):
    body = client.get("/api/health").json()
    assert body["connected_to_slack"] is False
    assert body["sent_to_slack"] is False
    assert body["label"] == LABEL


def test_notes_list_has_every_quarter_held_and_undismissed(client):
    body = client.get("/api/notes").json()
    assert len(body["notes"]) == 10
    for n in body["notes"]:
        assert n["decision"] == "HOLD"
        assert n["headline"].startswith("**Held: ")
        assert n["dismissed"] is False


def test_note_detail_returns_the_rendered_note(client):
    q = "2021-Q4"
    body = client.get(f"/api/notes/{q}").json()
    assert body["quarter"] == q
    assert body["note"].startswith("**Held: 2021-Q4**")
    assert body["dismissal"] is None
    assert body["label"] == LABEL


def test_unknown_or_malformed_quarter_is_404(client):
    assert client.get("/api/notes/2030-Q1").status_code == 404
    assert client.get("/api/notes/..%2Fdecision_status").status_code == 404
    assert client.get("/api/notes/2021-Q4/why/extra").status_code == 404


def test_why_lists_each_fact_with_file_and_query(client):
    body = client.get("/api/notes/2021-Q4/why").json()
    assert [f["fact"] for f in body["facts"]] == [
        "PRESSURE",
        "VOUCH",
        "RUSH",
        "BYPASS",
        "LONE_KEEPER",
    ]
    for f in body["facts"]:
        assert f["file"] in {PV_NAME, QS_NAME}
        assert f["queries"], f["fact"]
    assert body["rule"].startswith("unknown_input")
    assert "Show me why: 2021-Q4" in body["text"]


def test_simulate_reports_unavailable_when_hardening_file_missing(client):
    body = client.get("/api/notes/2021-Q4/simulate").json()
    assert body["available"] is False
    assert body["result"] is None
    assert "make harden" in body["reason"]
    assert body["source"] == "xz_hardening.json"


def test_simulate_reads_the_saved_hardening_file_when_present(results, client):
    saved = {"steps": [{"name": "second keeper", "takeover_cost_after": 2}]}
    (results / "xz_hardening.json").write_text(json.dumps(saved), encoding="utf-8")
    body = client.get("/api/notes/2021-Q4/simulate").json()
    assert body["available"] is True
    assert body["result"] == saved
    assert "computes nothing" in body["reason"]


def test_simulate_handles_an_unreadable_hardening_file(results, client):
    (results / "xz_hardening.json").write_text("{not json", encoding="utf-8")
    body = client.get("/api/notes/2021-Q4/simulate").json()
    assert body["available"] is False
    assert body["result"] is None


def test_dismiss_writes_one_local_line_and_is_idempotent(client, inbox):
    first = client.post("/api/notes/2021-Q4/dismiss", json={"reason": "  Already reviewed.  "})
    assert first.status_code == 200
    assert first.json()["already"] is False
    assert first.json()["dismissal"]["reason"] == "Already reviewed."
    assert first.json()["dismissal"]["sent_to_slack"] is False

    second = client.post("/api/notes/2021-Q4/dismiss", json={"reason": "Tapped twice."})
    assert second.json()["already"] is True
    assert second.json()["dismissal"]["reason"] == "Already reviewed."

    lines = inbox.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["quarter"] == "2021-Q4"


def test_dismissed_note_shows_as_dismissed_in_the_list(client):
    client.post("/api/notes/2022-Q1/dismiss", json={"reason": "Known release freeze."})
    flags = {n["quarter"]: n["dismissed"] for n in client.get("/api/notes").json()["notes"]}
    assert flags["2022-Q1"] is True
    assert flags["2021-Q4"] is False
    detail = client.get("/api/notes/2022-Q1").json()
    assert detail["dismissal"]["reason"] == "Known release freeze."


@pytest.mark.parametrize("reason", ["", "ab", "   ", "x" * 501])
def test_dismiss_rejects_empty_short_or_long_reasons(client, inbox, reason):
    r = client.post("/api/notes/2021-Q4/dismiss", json={"reason": reason})
    assert r.status_code == 422
    assert not inbox.exists()


def test_dismiss_unknown_quarter_is_404_and_writes_nothing(client, inbox):
    r = client.post("/api/notes/2030-Q1/dismiss", json={"reason": "Not a real quarter."})
    assert r.status_code == 404
    assert not inbox.exists()


def test_every_response_carries_a_label(client):
    paths = [
        "/api/health",
        "/api/notes",
        "/api/notes/2021-Q4",
        "/api/notes/2021-Q4/why",
        "/api/notes/2021-Q4/simulate",
    ]
    for p in paths:
        assert client.get(p).json()["label"] == LABEL, p


def test_no_note_served_by_the_api_contains_an_accusation(client):
    for quarter in _quarters(client):
        note = client.get(f"/api/notes/{quarter}").json()["note"]
        assert find_accusations(note) == [], quarter
        assert ends_with_question(note), quarter
        why = client.get(f"/api/notes/{quarter}/why").json()["text"]
        assert find_accusations(why) == [], quarter


def test_api_never_writes_outside_the_inbox_file(client, results, inbox, tmp_path):
    before = sorted(p.name for p in results.iterdir())
    client.post("/api/notes/2021-Q4/dismiss", json={"reason": "Checked by hand."})
    assert sorted(p.name for p in results.iterdir()) == before
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert written == [
        "inbox/dismissals.jsonl",
        "results/decision_status.json",
        "results/pressure_vouch_status.json",
        "results/xz_quarterly_status.json",
    ]


def test_static_ui_is_mounted_when_built(tmp_path, results, inbox):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>inbox</title>", encoding="utf-8")
    c = TestClient(create_app(results=results, inbox_file=inbox, static_dir=dist))
    assert "inbox" in c.get("/").text
    assert c.get("/api/health").status_code == 200
    assert Path(dist).exists()
