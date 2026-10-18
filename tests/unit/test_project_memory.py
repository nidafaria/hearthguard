"""Unit tests for per-project graph memory (Step A).

- Each project gets its own graph named hh_<project_slug>.
- The slug is the lowercased project name with unsafe characters replaced by underscores.
- Odd names ("", "../x", "A B/C", unicode) map to a safe slug and never escape the graph namespace.
- Writing a claim to project A: query project B gets nothing, query project A gets it back.
- Every read and write requires an explicit project name (no shared default graph).
"""

import re

import pytest

from core.graph.client import FalkorClient
from core.memory.project import (
    drop_project_graph,
    get_project_claims,
    list_claims,
    project_graph_name,
    project_slug,
    write_project_claim,
)


@pytest.fixture
def client() -> FalkorClient:
    return FalkorClient()


def test_project_slug_odd_names():
    """Odd names ("", "../x", "A B/C", unicode) map to a safe slug.

    Ensures names never escape the graph namespace.
    """
    cases = [
        ("Left-Pad", "left_pad", "hh_left_pad"),
        ("", "empty", "hh_empty"),
        ("../x", "___x", "hh____x"),
        ("A B/C", "a_b_c", "hh_a_b_c"),
        ("café-au-lait", "caf__au_lait", "hh_caf__au_lait"),
        ("プロジェクト", "______", "hh_______"),
        ("../../secret/path", "______secret_path", "hh_______secret_path"),
    ]

    for raw, expected_slug, expected_graph in cases:
        slug = project_slug(raw)
        graph = project_graph_name(raw)

        assert slug == expected_slug, f"Failed slug for {raw!r}: got {slug!r}"
        assert graph == expected_graph, f"Failed graph for {raw!r}: got {graph!r}"
        assert graph.startswith("hh_"), f"Graph name {graph} must start with 'hh_'"

        # Graph namespace isolation checks: never escape graph namespace
        assert ".." not in graph, f"Graph name {graph} must not contain '..'"
        assert "/" not in graph, f"Graph name {graph} must not contain '/'"
        assert "\\" not in graph, f"Graph name {graph} must not contain '\\'"
        assert re.match(r"^hh_[a-z0-9_]+$", graph), f"Graph name {graph} contains unsafe chars"


def test_write_and_query_project_memory_isolation(client):
    """Write claim to project A. Query project B gets nothing. Query project A gets it back."""
    proj_a = "Left-Pad"
    proj_b = "Right-Pad"

    # Clean up any leftover test graphs
    drop_project_graph(proj_a, client)
    drop_project_graph(proj_b, client)

    try:
        # 1. Initially both have zero claims
        assert get_project_claims(proj_a, client) == []
        assert get_project_claims(proj_b, client) == []

        # 2. Write a claim to project A
        claim_data = {
            "id": "claim-leftpad-01",
            "kind": "PRESSURE",
            "author": "maintainer@leftpad.invalid",
            "quote": "Please publish version 1.0 immediately",
            "confidence": 0.95,
            "at": 1700000000,
        }
        written = write_project_claim(proj_a, claim_data, client)
        assert written["claim_id"] == "claim-leftpad-01"
        assert written["graph"] == "hh_left_pad"

        # 3. Query project B and get nothing
        claims_b = get_project_claims(proj_b, client)
        assert claims_b == [], f"Expected empty list for project B, got {claims_b}"

        # 4. Query project A and get it back
        claims_a = get_project_claims(proj_a, client)
        assert len(claims_a) == 1
        retrieved = claims_a[0]
        assert retrieved["id"] == "claim-leftpad-01"
        assert retrieved["kind"] == "PRESSURE"
        assert retrieved["confidence"] == 0.95
        assert retrieved["quote"] == "Please publish version 1.0 immediately"
        assert retrieved["at"] == 1700000000

        # Also test list_claims alias
        claims_alias = list_claims(proj_a, client)
        assert claims_alias == claims_a

    finally:
        drop_project_graph(proj_a, client)
        drop_project_graph(proj_b, client)


def test_no_shared_default_graph():
    """Every read and write requires an explicit project name."""
    with pytest.raises(TypeError):
        # Omission of project argument must fail
        write_project_claim(claim={"id": "x"})  # type: ignore

    with pytest.raises(TypeError):
        # Omission of project argument must fail
        get_project_claims()  # type: ignore
