"""The playbook graph on a real FalkorDB (docs/HEARTHGUARD.md 6.5). Writes only to a scratch
playbook graph whose name holds a test id, and drops it afterwards."""

import uuid

import pytest

from core.graph.client import FalkorClient
from core.learning import pipeline as pl
from core.learning import states
from core.playbook import store as pb

ORG_KEYS = {"org", "org_id", "note", "note_id", "actor", "actor_hid", "hid", "fid", "finding"}


@pytest.fixture
def graph():
    name = f"playbook_tst{uuid.uuid4().hex[:10]}"
    client = FalkorClient()
    yield name
    client.drop(name)


@pytest.fixture(scope="module")
def client():
    return FalkorClient()


@pytest.fixture(scope="module")
def suite():
    if not (pl.RESULTS / pl.SUITE).exists():
        pytest.skip("saved red-team suite absent")
    return pl.load_suite()


def _exc(suite, reason="these are our CI bots"):
    campaigns, real = suite
    return pl.learn(reason, campaigns, real)


def test_a_proposal_is_stored_once_with_its_state_and_gate_numbers(client, graph, suite):
    out = _exc(suite)
    pb.record(client, out, now=100, graph=graph)
    pb.record(client, out, now=200, graph=graph)  # a repeat changes nothing that matters
    listed = pb.list_exceptions(client, graph)
    assert len(listed["exceptions"]) == 1
    x = listed["exceptions"][0]
    assert x["id"] == out["exception_id"]
    assert x["state"] == states.SHADOW
    assert x["gate"]["planted_lost"] == 0
    assert x["gate"]["planted_total"] == 200
    assert x["agreements"] == 1 and x["created_at"] == 100  # the creating dismissal counts once


def test_the_playbook_holds_no_organisation_data(client, graph, suite):
    pb.record(client, _exc(suite), now=1, graph=graph)
    keys = set(pb.list_exceptions(client, graph)["exceptions"][0])
    assert not keys & ORG_KEYS
    assert keys <= {
        "id",
        "exception",
        "applies_to",
        "when",
        "effect",
        "state",
        "state_reason",
        "agreements",
        "created_at",
        "updated_at",
        "gate",
        "owner_approved_at",
    }


def test_the_detector_spec_hash_is_recorded_once(client, graph, suite):
    pb.record(client, _exc(suite), now=1, graph=graph)
    pb.record(client, _exc(suite, "these are our renovate bots"), now=2, graph=graph)
    spec = pb.list_exceptions(client, graph)["spec_hashes"]
    assert spec == [pb.spec_hash()]


def test_agreements_count_each_new_dismissal(client, graph, suite):
    out = _exc(suite)
    pb.record(client, out, now=1, graph=graph)
    assert pb.count_agreement(client, out["exception_id"], 2, graph) == 2
    assert pb.count_agreement(client, out["exception_id"], 3, graph) == 3


def test_an_owner_approves_a_shadow_exception_once(client, graph, suite):
    out = _exc(suite)
    pb.record(client, out, now=1, graph=graph)
    first = pb.approve(client, out["exception_id"], 5, graph)
    second = pb.approve(client, out["exception_id"], 6, graph)
    assert first["state"] == states.ADOPTED and first["owner_approved_at"] == 5
    assert second is None


def test_a_rejected_exception_is_kept_with_its_reason_and_cannot_be_approved(client, graph):
    bad = {
        "exception_id": "exc:0000000000000000",
        "template": {
            "exception": "vouch_is_not_bots",
            "applies_to": "move.VOUCH",
            "when": "actor.hid IN org.declared_handover",
            "effect": "exclude_actor_from_move",
        },
        "state": states.REJECTED,
        "state_reason": "gate: 18 planted campaign(s) lost",
        "gate": {"planted_lost": 18, "planted_total": 200, "passed": False},
    }
    pb.record(client, bad, now=1, graph=graph)
    x = pb.get(client, bad["exception_id"], graph)
    assert x["state"] == states.REJECTED and "18" in x["state_reason"]
    assert pb.approve(client, bad["exception_id"], 2, graph) is None
