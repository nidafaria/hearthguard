"""Grant records on a real FalkorDB org graph (spec §6.1). A second write adds nothing."""

from packs.oss.grants import write_records
from tests.fixtures.bd import q
from tests.unit.test_grants_mapping import GOOD_APPROVAL, GOOD_CAN, GOOD_GRANT


def _edges(client, org):
    return q(client, org, "MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY type(r)").result_set


def test_records_become_one_edge_each_and_a_rerun_changes_nothing(client, org_graph):
    g = f"org_{org_graph}"
    write_records(client, g, [GOOD_GRANT, GOOD_CAN, GOOD_APPROVAL])
    first = _edges(client, org_graph)
    # Hand-worked: GRANTED, CAN_GRANT, APPROVED, one each.
    assert first == [["APPROVED", 1], ["CAN_GRANT", 1], ["GRANTED", 1]]
    write_records(client, g, [GOOD_GRANT, GOOD_CAN, GOOD_APPROVAL])
    assert _edges(client, org_graph) == first


def test_empty_input_writes_nothing(client, org_graph):
    write_records(client, f"org_{org_graph}", [])
    assert q(client, org_graph, "MATCH (n) RETURN count(n)").result_set[0][0] == 1  # the Org only
