"""Mark callback done (spec 12.2, finance), on a real FalkorDB through the finance pack.

The tap records the verification on the Path of the bank change (`Path.verified = true`). The
frozen Bypass detector then reads the changed record: the callback property goes from DIFFERS to
MATCHES. Channel and approvers are not touched by a callback, so they still differ and the Bypass
still fires on those two. A double tap records once. Nothing is sent to anyone.
"""

import uuid

import pytest

from core.agents import callback
from core.detectors.bypass import bypass
from core.graph.client import FalkorClient
from eval import northbridge_case as nc
from packs.finance import mapping, parse

NOW = 1_700_000_000


@pytest.fixture()
def world():
    client = FalkorClient()
    org = "cb" + uuid.uuid4().hex[:8]
    graph = f"org_{org}"
    parsed = parse.parse_records(nc.load_dataset(), parse.default_salt())
    mapping.load(client, graph, parsed, nc.T_CASE, org)
    try:
        yield client, org, graph
    finally:
        client.drop(graph)


def _differing(client, org):
    res = bypass(client, org, nc.ATTACK_ACTION, nc.T_CASE, nc.TIMEOUT)
    return res.status, res.evidence["differing"]


def test_before_the_tap_all_three_properties_differ(world):
    client, org, _ = world
    assert _differing(client, org) == ("FIRED", ["channel", "callback", "approvers"])


def test_the_tap_resolves_the_callback_property_from_the_record(world):
    client, org, graph = world
    assert callback.mark_callback_done(client, graph, nc.ATTACK_ACTION, NOW) is True
    assert _differing(client, org) == ("FIRED", ["channel", "approvers"])


def test_a_double_tap_records_once(world):
    client, _, graph = world
    assert callback.mark_callback_done(client, graph, nc.ATTACK_ACTION, NOW) is True
    assert callback.mark_callback_done(client, graph, nc.ATTACK_ACTION, NOW + 5) is False
    marked = client.query(
        graph,
        "MATCH (:Action {ref: $r})-[:VIA]->(p:Path) RETURN p.verified, p.callback_marked_at",
        {"r": nc.ATTACK_ACTION},
        timeout_ms=nc.TIMEOUT,
    ).result_set
    assert marked == [[True, NOW]]


def test_an_unknown_action_is_not_marked_and_nothing_changes(world):
    client, org, graph = world
    assert callback.mark_callback_done(client, graph, "no-such-action", NOW) is False
    assert _differing(client, org) == ("FIRED", ["channel", "callback", "approvers"])


def test_only_bank_changes_can_be_marked(world):
    client, _, graph = world
    ref = client.query(
        graph,
        "MATCH (a:Action) WHERE a.kind <> 'bank_change' RETURN a.ref LIMIT 1",
        timeout_ms=nc.TIMEOUT,
    ).result_set[0][0]
    assert callback.mark_callback_done(client, graph, ref, NOW) is False
