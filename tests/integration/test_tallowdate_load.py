"""Synthetic tallowdate in org_tallowdate, on a real FalkorDB: idempotent, labelled, allowlisted."""

import json
from pathlib import Path

from core.graph.client import FalkorClient
from packs.oss.xz_graph import graph_counts
from redteam.load_tallowdate import GRAPH, NAMED, SOURCE, load
from tests.unit.conftest import needs_salt

# Loading the synthetic case hashes identifiers; the salt is in .env (git-ignored). Skip without it.
pytestmark = needs_salt

ROOT = Path(__file__).resolve().parents[2]
LOAD_JSON = ROOT / "eval" / "results" / "tallowdate_load.json"


def _case() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_load_is_idempotent():
    client = FalkorClient()
    load(client, _case())
    first = graph_counts(client, GRAPH)
    load(client, _case())
    second = graph_counts(client, GRAPH)
    assert first == second
    # The saved load counts cover the labels the loader writes. Normal nodes come from the metrics.
    saved = json.loads(LOAD_JSON.read_text(encoding="utf-8"))["counts_after_run_1"]
    loader_nodes = {"Action", "Actor", "Org", "Path"}
    loader_edges = {"DID", "VIA"}
    assert {k: v for k, v in first["nodes"].items() if k in loader_nodes} == {
        k: v for k, v in saved["nodes"].items() if k in loader_nodes
    }
    assert {k: v for k, v in first["edges"].items() if k in loader_edges} == {
        k: v for k, v in saved["edges"].items() if k in loader_edges
    }


def test_every_node_and_edge_is_synthetic():
    client = FalkorClient()
    load(client, _case())
    nodes = client.query(
        GRAPH, "MATCH (n) WHERE n.synthetic IS NULL OR n.synthetic <> true RETURN count(n)"
    ).result_set[0][0]
    edges = client.query(
        GRAPH,
        "MATCH ()-[r]->() WHERE r.synthetic IS NULL OR r.synthetic <> true RETURN count(r)",
    ).result_set[0][0]
    assert nodes == 0
    assert edges == 0


def test_only_fictional_names_are_stored():
    client = FalkorClient()
    load(client, _case())
    names = {
        row[0]
        for row in client.query(
            GRAPH, "MATCH (a:Actor) WHERE a.name IS NOT NULL RETURN a.name"
        ).result_set
    }
    assert names == set(NAMED)
    # No node or edge has a property named like a person, and no other property holds a name.
    keys = client.query(GRAPH, "MATCH (n) UNWIND keys(n) AS k RETURN DISTINCT k").result_set
    assert {k for (k,) in keys} <= {
        "hid",
        "kind",
        "first_seen_in_org",
        "name",
        "planted",
        "campaign_id",
        "synthetic",
        "id",
        "pack",
        "connected_by",
        "ref",
        "at",
        "case",
        "channel",
        "verified",
        "approvers",
        # Normal nodes, written by the metrics step (redteam/tallowdate_normal.py).
        "metric",
        "scope",
        "window",
        "computed_at",
        "value",
    }
