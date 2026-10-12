"""Remembered-normal metrics on small hand-built graphs, real FalkorDB. Times are days * 86400."""

import pytest

from core.graph.as_of import MissingAsOfError
from core.graph.client import FalkorClient
from core.normal import metrics

D = 86_400


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def org(client, request):
    org = "nm_" + request.node.name.removeprefix("test_")[:40]
    client.drop(metrics.graph_for(org))
    yield org
    client.drop(metrics.graph_for(org))


def add_commit(client, org, ref, hid, day):
    client.query(
        metrics.graph_for(org),
        """MERGE (a:Actor {hid: $hid})
           MERGE (c:Action {ref: $ref}) SET c.kind = 'commit', c.at = $at
           MERGE (a)-[d:DID]->(c) SET d.at = $at""",
        {"hid": hid, "ref": ref, "at": day * D},
    )


def add_release(client, org, ref, day, channel="git"):
    client.query(
        metrics.graph_for(org),
        """MERGE (r:Action {ref: $ref}) SET r.kind = 'release', r.at = $at
           MERGE (p:Path {channel: $ch, verified: false})
           MERGE (r)-[:VIA]->(p)""",
        {"ref": ref, "at": day * D, "ch": channel},
    )


def test_cadence_is_median_gap_in_days(client, org):
    # Commits on days 0, 1, 3, 7: gaps 1, 2, 4, median 2. At T=day 3: gaps 1, 2, median 1.5.
    for i, day in enumerate([0, 1, 3, 7]):
        add_commit(client, org, f"c{i}", "a1", day)
    at7 = metrics.commit_cadence_days(client, org, 7 * D)
    at3 = metrics.commit_cadence_days(client, org, 3 * D)
    assert (at7.status, at7.value, at7.n) == (metrics.COMPUTED, 2.0, 3)
    assert (at3.status, at3.value, at3.n) == (metrics.COMPUTED, 1.5, 2)
    assert at7.query and "$T" in at7.query and at7.query_ms is not None


def test_metric_at_T_does_not_change_when_a_later_commit_is_added(client, org):
    for i, day in enumerate([0, 1, 3, 7]):
        add_commit(client, org, f"c{i}", f"a{i % 2}", day)
    T = 7 * D
    before = (
        metrics.commit_cadence_days(client, org, T).value,
        metrics.active_keepers_as_of_T(client, org, T).value,
    )
    add_commit(client, org, "later", "a_new", 100)  # a commit from the future of T
    after = (
        metrics.commit_cadence_days(client, org, T).value,
        metrics.active_keepers_as_of_T(client, org, T).value,
    )
    assert before == after == (2.0, 2)


def test_commit_after_T_is_excluded(client, org):
    add_commit(client, org, "early", "a1", 10)
    add_commit(client, org, "late", "a2", 50)  # after T, from a different actor
    assert metrics.active_keepers_as_of_T(client, org, 20 * D).value == 1
    assert metrics.active_keepers_as_of_T(client, org, 60 * D).value == 2


def test_active_keepers_window_is_trailing_90_days(client, org):
    add_commit(client, org, "old", "a1", 0)
    add_commit(client, org, "recent", "a2", 150)
    # At day 200 the window is (110, 200]: only a2 is active. At day 80 the window holds a1 only.
    assert metrics.active_keepers_as_of_T(client, org, 200 * D).value == 1
    assert metrics.active_keepers_as_of_T(client, org, 80 * D).value == 1
    assert metrics.active_keepers_as_of_T(client, org, 1000 * D).value == 0


def test_release_channel_is_most_common_in_window(client, org):
    add_release(client, org, "r1", 10, "git")
    add_release(client, org, "r2", 20, "git")
    add_release(client, org, "r3", 30, "tarball")
    res = metrics.release_channel_as_of_T(client, org, 40 * D)
    assert (res.status, res.value, res.n) == (metrics.COMPUTED, "git", 3)
    # At day 750 the window is (20, 750] days: r1 and r2 (days 10, 20) are out, r3 (day 30) is in.
    later = metrics.release_channel_as_of_T(client, org, 750 * D)
    assert later.value == "tarball"


def test_metrics_not_computed_when_data_is_missing(client, org):
    add_commit(client, org, "only", "a1", 5)
    cadence = metrics.commit_cadence_days(client, org, 10 * D)
    channel = metrics.release_channel_as_of_T(client, org, 10 * D)
    assert cadence.status == metrics.NOT_COMPUTED and "fewer than 2" in cadence.reason
    assert channel.status == metrics.NOT_COMPUTED and "no releases" in channel.reason
    assert cadence.value is None and channel.value is None


def test_open_freeze_metrics_are_not_computed():
    res = metrics.keeper_activity_median_90d(0)
    assert res.status == metrics.NOT_COMPUTED and "§7.6" in res.reason and res.query is None
    assert metrics.grant_days(0).status == metrics.NOT_COMPUTED
    assert metrics.trusted_actor_set(0).status == metrics.NOT_COMPUTED


def test_store_is_idempotent_and_skips_not_computed(client, org):
    for i, day in enumerate([0, 1, 3]):
        add_commit(client, org, f"c{i}", "a1", day)
    res = metrics.commit_cadence_days(client, org, 3 * D)
    metrics.store(client, org, res)
    metrics.store(client, org, res)
    metrics.store(client, org, metrics.keeper_activity_median_90d(3 * D))  # nothing to store
    g = metrics.graph_for(org)
    n = client.query(g, "MATCH (n:Normal)-[:OF]->(:Org {id: $o}) RETURN count(n)", {"o": org})
    assert n.result_set[0][0] == 1
    stored = client.query(g, "MATCH (n:Normal) RETURN n.metric, n.value, n.computed_at")
    assert stored.result_set == [["cadence_days", 1.5, 3 * D]]


def test_metric_refuses_missing_T(client, org):
    with pytest.raises(MissingAsOfError):
        metrics.commit_cadence_days(client, org, None)
