"""The task board on a real FalkorDB (docs/HEARTHGUARD.md 8.2): leases, priority order, stale-result
rejection, holds, requests, hardening, AgentStep and resume. Scratch org graphs only."""

import pytest

from core.agents import agent_step
from core.board import board, hardening, requests
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from tests.integration.scratch_graphs import drop_owned, new_org_id


@pytest.fixture
def org():
    client = FalkorClient()
    oid = new_org_id()
    graph = f"org_{oid}"
    client.drop(graph)
    apply_schema(client, graph)
    yield client, graph
    drop_owned(client, oid)


def add(c, g, tid, prio=0, at=0):
    return board.add_task(c, g, tid, "kind", prio, at, synthetic=True)


def test_adding_a_task_twice_leaves_one(org):
    c, g = org
    assert add(c, g, "t1") is True
    assert add(c, g, "t1") is False
    assert board.tasks_by_status(c, g) == {"OPEN": 1}


def test_claim_order_is_priority_then_age_then_id(org):
    c, g = org
    add(c, g, "old-low", prio=1, at=1)
    add(c, g, "new-high", prio=9, at=50)
    add(c, g, "old-high-b", prio=9, at=10)
    add(c, g, "old-high-a", prio=9, at=10)
    got = [board.claim(c, g, "a", now=100) for _ in range(5)]
    assert got == ["old-high-a", "old-high-b", "new-high", "old-low", None]


def test_an_expired_lease_reopens_the_task_for_another_agent(org):
    c, g = org
    add(c, g, "t1")
    assert board.claim(c, g, "a1", now=0) == "t1"
    assert board.claim(c, g, "a2", now=board.LEASE_MS - 1) is None  # lease still valid
    assert board.claim(c, g, "a2", now=board.LEASE_MS + 1) == "t1"  # expired -> claimable
    t = board.get_task(c, g, "t1")
    assert t["claimed_by"] == "a2" and t["attempts"] == 2


def test_the_old_holder_cannot_hand_in_after_a_takeover(org):
    c, g = org
    add(c, g, "t1")
    board.claim(c, g, "a1", now=0)
    board.claim(c, g, "a2", now=board.LEASE_MS + 1)
    assert board.complete(c, g, "t1", "a1", now=board.LEASE_MS + 2) == board.NOT_OWNER
    assert board.complete(c, g, "t1", "a2", now=board.LEASE_MS + 3) == board.ACCEPTED
    assert board.complete(c, g, "t1", "a2", now=board.LEASE_MS + 4) == board.NOT_OWNER
    assert board.complete(c, g, "nope", "a2", now=1) == board.NO_TASK


def test_a_result_computed_on_an_older_graph_is_rejected_and_requeued(org):
    c, g = org
    add(c, g, "t1")
    board.claim(c, g, "a1", now=0)
    assert board.get_task(c, g, "t1")["input_version"] == 0
    board.bump_version(c, g)  # the graph changed while a1 was working
    assert board.complete(c, g, "t1", "a1", now=5) == board.STALE_REQUEUED
    t = board.get_task(c, g, "t1")
    assert t["status"] == "OPEN" and t["requeues"] == 1 and "claimed_by" not in t
    # the next claim records the new version and its result is accepted
    assert board.claim(c, g, "a1", now=10) == "t1"
    assert board.get_task(c, g, "t1")["input_version"] == 1
    assert board.complete(c, g, "t1", "a1", now=11) == board.ACCEPTED


def test_renew_extends_only_for_the_holder(org):
    c, g = org
    add(c, g, "t1")
    board.claim(c, g, "a1", now=0)
    assert board.renew(c, g, "t1", "a1", now=20_000) is True
    assert board.renew(c, g, "t1", "a2", now=20_000) is False
    assert board.claim(c, g, "a2", now=board.LEASE_MS + 1) is None  # renewed to 50 000


def test_a_held_task_is_not_claimed_and_goes_to_human_review_at_its_deadline(org):
    c, g = org
    add(c, g, "t1")
    board.claim(c, g, "a1", now=0)
    assert board.hold(c, g, "t1", "REPLAN_LIMIT", "QUERY_TIMEOUT", until=1000)
    assert board.claim(c, g, "a2", now=10**9) is None
    assert board.expire_holds(c, g, now=999) == 0
    assert board.expire_holds(c, g, now=1000) == 1
    t = board.get_task(c, g, "t1")
    assert t["status"] == board.HUMAN_REVIEW and t["failure_type"] == "QUERY_TIMEOUT"
    assert board.claim(c, g, "a2", now=10**9) is None


def test_a_note_is_sent_once(org):
    c, g = org
    c.query(g, "CREATE (:Finding {id: 'f1', status: 'open'})")
    assert board.send_note(c, g, "f1", "h1", now=1) is True
    assert board.send_note(c, g, "f1", "h1", now=2) is False
    assert board.send_note(c, g, "f1", "h2", now=3) is True
    n = c.query(g, "MATCH (n:Note)-[:FOR]->(:Finding {id: 'f1'}) RETURN count(n)").result_set
    assert n[0][0] == 2


def test_an_objection_holds_the_finding_until_the_request_is_answered(org):
    c, g = org
    c.query(g, "CREATE (:Finding {id: 'f1', status: 'open'})")
    assert requests.raise_objection(
        c, g, "f1", "o1", "is there an in-repo handover announcement?", "r1",
        "skeptic", "investigator", "is there an in-repo handover announcement?", # noqa: E501
    )  # fmt: skip
    # raising it again changes nothing
    requests.raise_objection(c, g, "f1", "o1", "x", "r1", "skeptic", "investigator", "q")
    status = lambda: c.query(g, "MATCH (f:Finding {id:'f1'}) RETURN f.status").result_set[0][0]  # noqa: E731
    assert status() == "held"
    assert [r["id"] for r in requests.open_requests(c, g, "f1")] == ["r1"]
    assert requests.answer_request(c, g, "r1", "no announcement found", now=5) is True
    assert status() == "open" and requests.open_requests(c, g, "f1") == []
    assert requests.answer_request(c, g, "r1", "again", now=6) is False  # already answered


def test_two_requests_both_must_be_answered(org):
    c, g = org
    c.query(g, "CREATE (:Finding {id: 'f1', status: 'open'})")
    requests.raise_objection(c, g, "f1", "o1", "a", "r1", "skeptic", "investigator", "q1")
    requests.raise_objection(c, g, "f1", "o2", "b", "r2", "skeptic", "investigator", "q2")
    assert requests.answer_request(c, g, "r1", "ok", now=1) is False
    assert requests.answer_request(c, g, "r2", "ok", now=2) is True


def test_a_dismissed_finding_is_not_reopened(org):
    c, g = org
    c.query(g, "CREATE (:Finding {id: 'f1', status: 'dismissed'})")
    assert not requests.raise_objection(c, g, "f1", "o1", "a", "r1", "skeptic", "inv", "q")
    assert c.query(g, "MATCH (f:Finding) RETURN f.status").result_set[0][0] == "dismissed"


def test_hardening_steps_are_merged_once(org):
    c, g = org
    nums = {"cost_before": 1, "cost_after": 2, "guardians_before": 1, "guardians_after": 2}
    assert hardening.record_hardening(c, g, "x", "run1", "s1", nums, synthetic=True) is True
    assert hardening.record_hardening(c, g, "x", "run1", "s1", nums, synthetic=True) is False
    hardening.record_hardening(c, g, "x", "run1", "s2", {"cost_before": 2, "cost_after": 3})
    steps = hardening.hardening_steps(c, g, "run1")
    assert [s["step"] for s in steps] == ["s1", "s2"]
    assert steps[0]["cost_after"] == 2 and steps[0]["synthetic"] is True


def test_agent_steps_are_numbered_and_logged_per_task(org):
    c, g = org
    add(c, g, "t1")
    assert (
        agent_step.log_step(c, g, "t1", "a1", "takeover_cost", "price the path", 12.5, "r1", 0, 1)
        == 0
    )
    assert agent_step.log_step(c, g, "t1", "a1", "guardians", "count cut", 3.0, "r2", 1, 2) == 1
    assert agent_step.log_step(c, g, "missing", "a1", "x", "x", 0, None, 0, 3) is None
    steps = agent_step.steps_for(c, g, "t1")
    assert [s["tool"] for s in steps] == ["takeover_cost", "guardians"]
    assert steps[1]["llm_calls"] == 1 and steps[0]["ms"] == 12.5


def test_a_second_agent_resumes_from_the_graph_after_a_crash(org):
    c, g = org
    add(c, g, "t1")
    board.claim(c, g, "crashed", now=0)
    agent_step.log_step(c, g, "t1", "crashed", "takeover_cost", "step 1", 5, "ref-1", 0, 1)
    agent_step.log_step(c, g, "t1", "crashed", "guardians", "step 2", 5, None, 1, 2)
    # a new process: a new client object, nothing carried over in memory
    c2 = FalkorClient()
    assert board.claim(c2, g, "rescuer", now=board.LEASE_MS + 1) == "t1"
    state = agent_step.resume_state(c2, g, "t1")
    assert state["tools_done"] == ["takeover_cost"]  # guardians had no stored result: redo it
    assert state["llm_calls"] == 1 and state["last_agent"] == "crashed"
    assert board.complete(c2, g, "t1", "rescuer", now=board.LEASE_MS + 5) == board.ACCEPTED
