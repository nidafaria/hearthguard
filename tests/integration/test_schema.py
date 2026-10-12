"""Schema: §6.6 constraints and indexes on the real container. Idempotent by construction."""

import pytest
from redis.exceptions import ResponseError

from core.graph.client import FalkorClient
from core.graph.schema import (
    RANGE_NODE_INDEXES,
    RANGE_REL_INDEXES,
    UNIQUE_NODE_KEYS,
    apply_schema,
    list_constraints,
)


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def g(client, request):
    name = "schema_" + request.node.name.removeprefix("test_")
    client.drop(name)
    yield name
    client.drop(name)


def index_pairs(client: FalkorClient, graph: str) -> set[tuple[str, str]]:
    r = client.query(graph, "CALL db.indexes() YIELD label, properties RETURN label, properties")
    return {(label, prop) for label, props in r.result_set for prop in props}


def unique_pairs(client: FalkorClient, graph: str) -> set[tuple[str, str]]:
    return {
        (c["label"], c["properties"][0])
        for c in list_constraints(client, graph)
        if c["type"] == "UNIQUE"
    }


def test_apply_schema_twice_leaves_same_constraints_and_indexes(client, g):
    apply_schema(client, g)
    constraints_first = list_constraints(client, g)
    indexes_first = index_pairs(client, g)
    apply_schema(client, g)
    constraints_second = list_constraints(client, g)
    indexes_second = index_pairs(client, g)
    print(
        f"\n[schema] constraints run 1: {len(constraints_first)}, run 2: {len(constraints_second)}"
    )
    print(f"[schema] index pairs run 1: {len(indexes_first)}, run 2: {len(indexes_second)}")
    assert len(constraints_second) == len(constraints_first) == len(UNIQUE_NODE_KEYS)
    assert indexes_second == indexes_first


def test_every_unique_key_from_spec_is_present(client, g):
    apply_schema(client, g)
    assert unique_pairs(client, g) == set(UNIQUE_NODE_KEYS)


def test_range_indexes_from_spec_are_present(client, g):
    apply_schema(client, g)
    present = index_pairs(client, g)
    for pair in RANGE_NODE_INDEXES + RANGE_REL_INDEXES:
        assert pair in present, f"missing range index {pair}"


@pytest.mark.parametrize("label,prop", UNIQUE_NODE_KEYS)
def test_unique_constraint_rejects_duplicate(client, g, label, prop):
    apply_schema(client, g)
    client.query(g, f"CREATE (:{label} {{{prop}: 'dup-key'}})")
    with pytest.raises(ResponseError, match="unique constraint violation"):
        client.query(g, f"CREATE (:{label} {{{prop}: 'dup-key'}})")
    count = client.query(g, f"MATCH (n:{label}) RETURN count(n)").result_set[0][0]
    assert count == 1


def test_idempotent_merge_writes_one_node(client, g):
    apply_schema(client, g)
    for _ in range(2):
        client.query(g, "MERGE (:Actor {hid: 'a1'})")
    count = client.query(g, "MATCH (n:Actor) RETURN count(n)").result_set[0][0]
    assert count == 1
