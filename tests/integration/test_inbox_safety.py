"""Safety tests for the inbox (spec 12.2, rows 109 and 110) on a real FalkorDB.

No accusation in anything the inbox serves, double taps through the send path and the buttons,
and the inbox working the same with Slack absent, broken or never configured.
"""

import dataclasses

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.agents.cases import CASES, RESULTS
from slack_app.notify import SendLedger, UnimplementedSlackSender, send_note
from slack_app.rules import ends_with_question, find_accusations

pytestmark = pytest.mark.usefixtures("real_graphs_untouched")


@pytest.fixture
def api(tmp_path, scratch_orgs):
    cases = {
        "xz": dataclasses.replace(CASES["xz"], org=scratch_orgs["xz"]),
        "tallowdate": dataclasses.replace(CASES["tallowdate"], org=scratch_orgs["tallowdate"]),
    }
    return TestClient(create_app(results=RESULTS, inbox_file=tmp_path / "d.jsonl", cases=cases))


class BrokenSender:
    def __init__(self):
        self.calls = 0

    def deliver(self, recipient_id, text):
        self.calls += 1
        raise ConnectionError("slack down")


class FakeSender:
    def __init__(self):
        self.calls = []

    def deliver(self, recipient_id, text):
        self.calls.append(text)
        return "m1"


def _quarters(api, case):
    return [n["quarter"] for n in api.get(f"/api/inbox/{case}/notes").json()["notes"]]


@pytest.mark.parametrize("case", ["xz", "tallowdate"])
def test_no_inbox_text_is_an_accusation_and_every_note_asks(api, case):
    quarters = _quarters(api, case)
    assert quarters
    for q in quarters:
        thread = api.get(f"/api/inbox/{case}/notes/{q}").json()
        assert find_accusations(thread["note"]) == [], (case, q)
        assert ends_with_question(thread["note"]), (case, q)
        for kind in ("boundary_reply", "invite_keeper"):
            d = api.post(f"/api/inbox/{case}/notes/{q}/draft", json={"kind": kind}).json()
            assert find_accusations(d["draft"]["body"] if "body" in d["draft"] else str(d)) == []
        for question in thread["suggested_questions"]:
            a = api.post(f"/api/inbox/{case}/notes/{q}/ask", json={"question": question}).json()
            assert find_accusations(a["answer"]) == [], (case, q, question)


@pytest.mark.parametrize("case", ["xz", "tallowdate"])
def test_the_sent_note_is_the_inbox_note_and_a_double_tap_sends_once(api, case):
    q = _quarters(api, case)[0]
    note = api.get(f"/api/inbox/{case}/notes/{q}").json()["note"]
    s, ledger = FakeSender(), SendLedger()
    kw = dict(case_id=case, quarter=q, recipient="owner", recipient_id="U", text=note)
    assert send_note(s, ledger, **kw).sent
    assert send_note(s, ledger, **kw).status == "already_sent"
    assert s.calls == [note]


def test_slack_down_the_inbox_answers_the_same_and_buttons_still_work(api):
    case, q = "xz", _quarters(api, "xz")[0]
    before = api.get(f"/api/inbox/{case}/notes/{q}").json()
    for sender in (BrokenSender(), UnimplementedSlackSender(), None):
        r = send_note(
            sender,
            SendLedger(),
            case_id=case,
            quarter=q,
            recipient="owner",
            recipient_id="U",
            text=before["note"],
        )
        assert not r.sent
    after = api.get(f"/api/inbox/{case}/notes/{q}").json()
    assert after["note"] == before["note"] and after["controls"] == before["controls"]
    assert after["sent_to_slack"] is False and after["connected_to_slack"] is False
    assert api.post(f"/api/inbox/{case}/notes/{q}/snooze").status_code == 200
    d = api.post(f"/api/inbox/{case}/notes/{q}/dismiss", json={"reason": "Known maintainer"})
    assert d.status_code == 200


def test_a_failed_send_is_not_recorded_so_retry_works_when_slack_returns(api):
    case, q = "xz", _quarters(api, "xz")[0]
    note = api.get(f"/api/inbox/{case}/notes/{q}").json()["note"]
    ledger = SendLedger()
    kw = dict(case_id=case, quarter=q, recipient="owner", recipient_id="U", text=note)
    bad = BrokenSender()
    assert send_note(bad, ledger, **kw).status == "failed"
    good = FakeSender()
    assert send_note(good, ledger, **kw).sent and len(good.calls) == 1
