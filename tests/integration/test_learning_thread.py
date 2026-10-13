"""It's fine: a dismissal runs the learning step and the thread shows the result (spec 12.2).
Real FalkorDB. Org graphs are scratch; the playbook graph is a scratch one too."""

import dataclasses
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.inbox_actions import build_router
from core.agents.cases import CASES, RESULTS
from core.graph.client import FalkorClient

pytestmark = pytest.mark.usefixtures("real_graphs_untouched")

CI = "these are our CI bots: dependabot and renovate"
HANDOVER = "this was our announced handover to the company team"


@pytest.fixture
def playbook_graph():
    name = f"playbook_tst{uuid.uuid4().hex[:10]}"
    yield name
    FalkorClient().drop(name)


@pytest.fixture
def api(tmp_path, scratch_orgs, playbook_graph):
    cases = {
        "xz": dataclasses.replace(CASES["xz"], org=scratch_orgs["xz"]),
        "tallowdate": dataclasses.replace(CASES["tallowdate"], org=scratch_orgs["tallowdate"]),
    }
    app = FastAPI()
    app.include_router(
        build_router(
            RESULTS,
            tmp_path / "dismissals.jsonl",
            cases=cases,
            playbook_graph=playbook_graph,
        )
    )
    return TestClient(app)


def _dismiss(api, quarter, reason):
    r = api.post(f"/api/inbox/xz/notes/{quarter}/dismiss", json={"reason": reason})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_dismissal_with_a_bot_reason_is_learned_and_shown_in_the_thread(api, playbook_graph):
    body = _dismiss(api, "2021-Q4", CI)
    learned = body["learning"]
    assert learned["new"] is True
    assert learned["state"] == "Shadow"
    assert learned["template"]["applies_to"] == "move.PRESSURE"
    assert learned["gate"]["planted_lost"] == 0
    assert learned["gate"]["planted_total"] == 200
    assert learned["result_line"].startswith("tested against 200 planted attacks, 0 lost")
    assert learned["nothing_is_applied"] is True
    assert learned["playbook"]["id"] == learned["exception_id"]


def test_the_thread_reads_the_stored_result_back(api):
    _dismiss(api, "2021-Q4", CI)
    thread = api.get("/api/inbox/xz/notes/2021-Q4").json()
    assert thread["decisions"][0]["learning_state"] == "Shadow"
    assert thread["decisions"][0]["exception_id"].startswith("exc:")


def test_a_second_tap_learns_nothing_new_and_counts_no_agreement(api, playbook_graph):
    first = _dismiss(api, "2021-Q4", CI)["learning"]
    second = _dismiss(api, "2021-Q4", CI)["learning"]
    assert second["new"] is False
    assert second["exception_id"] == first["exception_id"]
    assert second["playbook"]["agreements"] == 1  # the first dismissal only


def test_a_different_dismissal_with_the_same_template_counts_an_agreement(api):
    _dismiss(api, "2021-Q4", CI)
    other = _dismiss(api, "2022-Q1", "dependabot and renovate are our CI bots")["learning"]
    assert other["exception_id"] is not None
    assert other["playbook"]["agreements"] == 2


def test_a_reason_with_no_building_block_goes_to_human_review_and_is_not_stored(api):
    learned = _dismiss(api, "2021-Q4", "I just do not like this one")["learning"]
    assert learned["state"] == "Human review"
    assert learned["exception_id"] is None
    assert learned["playbook"] is None
    assert len(learned["attempts"]) == 3


def test_the_playbook_endpoint_lists_the_exception_and_no_organisation_id(api, scratch_orgs):
    _dismiss(api, "2021-Q4", CI)
    doc = api.get("/api/inbox/playbook").json()
    assert doc["exceptions"] and doc["exceptions"][0]["state"] == "Shadow"
    text = str(doc)
    assert scratch_orgs["xz"] not in text
    assert "2021-Q4" not in text


def test_an_owner_approval_moves_a_shadow_exception_to_adopted_once(api):
    xid = _dismiss(api, "2021-Q4", CI)["learning"]["exception_id"]
    first = api.post(f"/api/inbox/playbook/{xid}/approve")
    second = api.post(f"/api/inbox/playbook/{xid}/approve")
    assert first.status_code == 200 and first.json()["state"] == "Adopted"
    assert second.status_code == 409


def test_a_bad_exception_id_is_refused(api):
    assert api.post("/api/inbox/playbook/not-an-id/approve").status_code == 404
