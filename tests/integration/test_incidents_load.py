"""event-stream and axios incident ingest (spec §3.1) on a real FalkorDB. No mocks.

Needs the cached public record under data/raw/incidents/ (git-ignored: `uv run python -m
eval.incidents_fetch`); without it the tests skip with that reason.

Hand-worked expectations from the cached files:
  - event-stream: 3.3.5 (2018-09-05) is the first release by a second publisher, and its
    maintainers list adds that publisher; 3.3.6 (2018-09-09) is in `time` but removed. So: one
    GRANTED edge (the newcomer) and two CAN_GRANT edges, and 3.3.6 is a release Action with no Path.
  - axios: 1.14.0 is a trusted-publisher release; 1.14.1 and 0.30.4 are removed, carry the
    'secondary' label, and have a Path with channel npm_user and ci False.
  - loading twice changes no count; no property holds an email address; the only named handle is
    right9ctrl; every secondary fact's quoted sentence is in the cached write-up.
"""

import uuid

import pytest

from eval import incidents_load as il
from packs.oss import incidents_graph as ig

pytestmark = pytest.mark.skipif(
    not (ig.RAW / "event_stream" / "npm_event-stream.json").is_file(),
    reason="data/raw/incidents is absent (git-ignored): run eval.incidents_fetch",
)


@pytest.fixture
def loaded(client):
    out = {}
    names = []
    try:
        for case in ig.CASES:
            doc = ig.build(case)
            graph = f"org_inc{uuid.uuid4().hex[:8]}"
            names.append(graph)
            ig.load(client, doc, graph)
            out[case] = (doc, graph)
        yield out
    finally:
        for g in names:
            client.drop(g)


def q(client, graph, cypher, params=None):
    return client.query(graph, cypher, params or {}, timeout_ms=60_000).result_set


def test_event_stream_grants_and_the_removed_release(client, loaded):
    doc, g = loaded["event_stream"]
    assert q(
        client, g, "MATCH ()-[x:GRANTED]->(:Privilege {kind:'npm_publish'}) RETURN count(x)"
    ) == [[1]]
    assert q(client, g, "MATCH ()-[x:CAN_GRANT]->(:Privilege) RETURN count(x)") == [[2]]
    r = q(
        client,
        g,
        "MATCH (x:Action {ref:'event-stream@3.3.6'}) OPTIONAL MATCH (x)-[:VIA]->(p:Path) "
        "RETURN x.kind, x.evidence, count(p)",
    )
    assert r == [["release", "registry_time_only", 0]]
    assert doc["personas"] and list(doc["personas"].values()) == ["right9ctrl"]


def test_axios_secondary_records_are_labelled(client, loaded):
    _doc, g = loaded["axios"]
    rows = q(
        client,
        g,
        "MATCH (x:Action)-[:VIA]->(p:Path) WHERE x.ref IN ['axios@1.14.1','axios@0.30.4'] "
        "RETURN x.ref, x.evidence, p.channel, p.ci ORDER BY x.ref",
    )
    assert rows == [
        ["axios@0.30.4", "secondary", "npm_user", False],
        ["axios@1.14.1", "secondary", "npm_user", False],
    ]
    legit = q(
        client,
        g,
        "MATCH (x:Action {ref:'axios@1.14.0'})-[:VIA]->(p:Path) "
        "RETURN p.channel, p.ci, p.provenance",
    )
    assert legit == [["npm_trusted_publisher", True, True]]


def test_second_load_changes_nothing_and_no_email_is_stored(client, loaded):
    for case, (doc, g) in loaded.items():
        before = ig.counts(client, g)
        assert ig.load(client, doc, g) == before, case
        assert il.email_hits(client, g) == [], case


def test_secondary_quotes_are_in_the_cached_source():
    facts = ig.secondary_facts()
    assert set(facts) == set(ig.AXIOS_SECONDARY_FACTS)


def test_a_missing_quote_is_refused(tmp_path):
    (tmp_path / "axios").mkdir()
    (tmp_path / "axios" / "stepsecurity_writeup.html").write_text("<p>nothing here</p>")
    with pytest.raises(ValueError):
        ig.secondary_facts(tmp_path)


def test_evidence_file_matches_the_graph():
    import json

    d = json.loads((ig.ROOT / "eval" / "results" / "incidents_load.json").read_text("utf-8"))
    for c in d["cases"].values():
        assert c["idempotent"] is True and c["email_like_properties"] == []
        assert c["counts_after_load_1"] == c["counts_after_load_2"]
