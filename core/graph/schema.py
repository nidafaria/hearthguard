"""Org graph schema: unique constraints and range indexes from docs/HEARTHGUARD.md §6.6.

FalkorDB 6.0.2 behaviour (docs/VERIFIED.md):
- Cypher `CREATE CONSTRAINT` is refused. Constraints use the GRAPH.CONSTRAINT command.
- A UNIQUE constraint needs an exact-match (range) index on the same property first.
- Creating an index that already exists is a silent no-op.
- Creating a constraint that already exists is an error, so apply_schema checks first.
"""

from typing import Any

from core.graph.client import FalkorClient

# (label, property). §6.6: Actor.hid, Action.ref, Claim.id, Finding.id, Note.id, Task.id, Place.ref.
UNIQUE_NODE_KEYS: tuple[tuple[str, str], ...] = (
    ("Actor", "hid"),
    ("Action", "ref"),
    ("Claim", "id"),
    ("Finding", "id"),
    ("Note", "id"),
    ("Task", "id"),
    ("Place", "ref"),
)

# Range indexes on every node property named `at` in §6.1.
RANGE_NODE_INDEXES: tuple[tuple[str, str], ...] = (
    ("Action", "at"),
    ("Claim", "at"),
    ("Span", "at"),
    ("Finding", "at"),
    ("OwnerDecision", "at"),
    ("Draft", "at"),
    ("AgentStep", "at"),
)

# Range indexes on relationship properties: every `at` on an edge in §6.1, plus §6.6's since.
RANGE_REL_INDEXES: tuple[tuple[str, str], ...] = (
    ("DID", "at"),
    ("GRANTED", "at"),
    ("APPROVED", "at"),
    ("PARTICIPATES_IN", "since"),
)


def range_indexes(client: FalkorClient, graph: str) -> set[tuple[str, str]]:
    """(label or relationship type, property) pairs that have a RANGE index."""
    r = client.query(graph, "CALL db.indexes() YIELD label, properties, types RETURN label, types")
    found: set[tuple[str, str]] = set()
    for label, types in r.result_set:
        for prop, kinds in types.items():
            if "RANGE" in kinds:
                found.add((label, prop))
    return found


def _range_node_index(
    client: FalkorClient, graph: str, label: str, prop: str, present: set[tuple[str, str]]
) -> None:
    # A repeated CREATE INDEX fails once a UNIQUE constraint sits on the same property,
    # so check first.
    if (label, prop) in present:
        return
    client.query(graph, f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
    present.add((label, prop))


def _range_rel_index(
    client: FalkorClient, graph: str, rel: str, prop: str, present: set[tuple[str, str]]
) -> None:
    if (rel, prop) in present:
        return
    client.query(graph, f"CREATE INDEX FOR ()-[r:{rel}]-() ON (r.{prop})")
    present.add((rel, prop))


def _unique_exists(client: FalkorClient, graph: str, label: str, prop: str) -> bool:
    for row in list_constraints(client, graph):
        if row["type"] == "UNIQUE" and row["label"] == label and row["properties"] == [prop]:
            return True
    return False


def _unique_constraint(client: FalkorClient, graph: str, label: str, prop: str) -> None:
    if _unique_exists(client, graph, label, prop):
        return
    client.db.execute_command(
        "GRAPH.CONSTRAINT", "CREATE", graph, "UNIQUE", "NODE", label, "PROPERTIES", "1", prop
    )


def list_constraints(client: FalkorClient, graph: str) -> list[dict[str, Any]]:
    r = client.query(
        graph,
        "CALL db.constraints() YIELD type, label, properties, status "
        "RETURN type, label, properties, status",
    )
    return [
        {"type": t, "label": lbl, "properties": list(props), "status": status}
        for t, lbl, props, status in r.result_set
    ]


def apply_schema(client: FalkorClient, graph: str) -> None:
    """Create the §6.6 constraints and indexes on `graph`. Safe to run any number of times."""
    present = range_indexes(client, graph)
    for label, prop in UNIQUE_NODE_KEYS:
        # A UNIQUE constraint needs its exact-match index first.
        _range_node_index(client, graph, label, prop, present)
        _unique_constraint(client, graph, label, prop)
    for label, prop in RANGE_NODE_INDEXES:
        _range_node_index(client, graph, label, prop, present)
    for rel, prop in RANGE_REL_INDEXES:
        _range_rel_index(client, graph, rel, prop, present)
