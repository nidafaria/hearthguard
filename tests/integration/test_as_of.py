"""As-of-T helper: refuses a missing T before any server call, and filters events at <= T."""

import pytest

from core.graph.as_of import MissingAsOfError, as_of_fragment, run_as_of, with_as_of
from core.graph.client import FalkorClient


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture(scope="module")
def dead_client() -> FalkorClient:
    # Nothing listens on port 1. Any call that reaches the network would fail with a
    # connection error, so a MissingAsOfError proves the check ran first.
    return FalkorClient(host="localhost", port=1)


@pytest.fixture
def g(client, request):
    name = "asof_" + request.node.name.removeprefix("test_")
    client.drop(name)
    yield name
    client.drop(name)


def test_fragment_is_parameterised():
    assert as_of_fragment("e") == "e.at <= $T"
    assert as_of_fragment("e", "since") == "e.since <= $T"


def test_fragment_rejects_non_identifiers():
    with pytest.raises(ValueError):
        as_of_fragment("e; DROP")


def test_with_as_of_refuses_none():
    with pytest.raises(MissingAsOfError):
        with_as_of({}, None)


def test_missing_T_is_refused_before_server(dead_client):
    with pytest.raises(MissingAsOfError):
        run_as_of(dead_client, "org_x", "MATCH (e:Action) WHERE e.at <= $T RETURN e.ref LIMIT 5")


def test_T_none_is_refused_before_server(dead_client):
    with pytest.raises(MissingAsOfError):
        run_as_of(
            dead_client,
            "org_x",
            "MATCH (e:Action) WHERE e.at <= $T RETURN e.ref LIMIT 5",
            {"T": None},
        )


def test_query_without_T_placeholder_is_refused_before_server(dead_client):
    with pytest.raises(MissingAsOfError, match="reference"):
        run_as_of(dead_client, "org_x", "MATCH (e:Action) RETURN e.ref LIMIT 5", {"T": 1})


def test_T_filters_events_on_real_graph(client, g):
    client.query(
        g,
        """CREATE (:Action {ref: 'e1', at: 1}), (:Action {ref: 'e2', at: 2}),
                  (:Action {ref: 'e3', at: 3})""",
    )
    cypher = (
        "MATCH (e:Action) WHERE "
        + as_of_fragment("e")
        + " RETURN e.ref AS ref ORDER BY ref LIMIT 100"
    )
    at2 = run_as_of(client, g, cypher, {"T": 2}).result_set
    at0 = run_as_of(client, g, cypher, {"T": 0}).result_set
    at3 = run_as_of(client, g, cypher, {"T": 3}).result_set
    print(f"\n[as-of] T=0 -> {at0}, T=2 -> {at2}, T=3 -> {at3}")
    assert [r[0] for r in at0] == []
    assert [r[0] for r in at2] == ["e1", "e2"]
    assert [r[0] for r in at3] == ["e1", "e2", "e3"]
