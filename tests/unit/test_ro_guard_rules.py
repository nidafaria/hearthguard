"""Pure checks of the read-only guard. No server needed."""

import pytest

from core.graph.ro_guard import MAX_LIMIT, ReadOnlyViolation, check_read_only

GOOD = [
    "MATCH (n:Action) RETURN n.ref LIMIT 10",
    "MATCH (n:Action) WHERE n.at <= $T RETURN n.ref AS ref LIMIT 100",
    "MATCH (n) RETURN count(n) AS c LIMIT 1",
    "CALL db.idx.fulltext.queryNodes('Span', 'hello') YIELD node RETURN node.text LIMIT 5",
    # Write words inside a string, a comment or a backtick name are text, not writes.
    "MATCH (n) WHERE n.note = 'please CREATE nothing' RETURN n LIMIT 3",
    "MATCH (n) // DELETE everything\nRETURN n LIMIT 3",
    "MATCH (n) RETURN n.`SET` AS s LIMIT 3",
    "MATCH (n) RETURN n.offset AS o LIMIT 3",
]

BAD = [
    ("CREATE (:X)", "CREATE"),
    ("MATCH (n) SET n.x = 1 RETURN n LIMIT 1", "SET"),
    ("MATCH (n) DELETE n LIMIT 1", "DELETE"),
    ("MATCH (n) DETACH DELETE n LIMIT 1", "DETACH"),
    ("MATCH (n) REMOVE n.x RETURN n LIMIT 1", "REMOVE"),
    ("MERGE (n:X {id: 1}) RETURN n LIMIT 1", "MERGE"),
    ("MATCH (n) FOREACH (x IN [1] | SET n.x = x) RETURN n LIMIT 1", "FOREACH"),
    ("LOAD CSV FROM 'file:///x' AS row RETURN row LIMIT 1", "LOAD"),
    ("MATCH (n) WITH n CREATE (m) RETURN m LIMIT 1", "CREATE"),
    ("CREATE FULLTEXT INDEX FOR (n:Span) ON (n.text)", "CREATE"),
]


@pytest.mark.parametrize("cypher", GOOD)
def test_reads_pass(cypher):
    check_read_only(cypher)


@pytest.mark.parametrize("cypher,keyword", BAD)
def test_writes_are_rejected(cypher, keyword):
    # The guard names the first write keyword it finds, so only the rejection is asserted here.
    with pytest.raises(ReadOnlyViolation, match="write keyword|index create/drop"):
        check_read_only(cypher)


def test_index_create_procedure_is_rejected():
    with pytest.raises(ReadOnlyViolation, match="index create/drop"):
        check_read_only(
            "CALL db.idx.fulltext.createNodeIndex('Span', 'text') YIELD label RETURN label LIMIT 1"
        )


def test_query_without_limit_is_rejected():
    with pytest.raises(ReadOnlyViolation, match="LIMIT"):
        check_read_only("MATCH (n) RETURN n")


def test_limit_over_cap_is_rejected():
    with pytest.raises(ReadOnlyViolation, match="at most"):
        check_read_only(f"MATCH (n) RETURN n LIMIT {MAX_LIMIT + 1}")


def test_limit_parameter_is_rejected():
    # The cap can only be checked on a literal number.
    with pytest.raises(ReadOnlyViolation, match="literal"):
        check_read_only("MATCH (n) RETURN n LIMIT $k")
