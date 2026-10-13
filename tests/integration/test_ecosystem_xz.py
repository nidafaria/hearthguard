"""ecosystem_xz against the real FalkorDB container (no mocks).

Loads into a scratch graph so the real `ecosystem_xz` is never touched. The public records come
from data/raw/ecosystem/, fetched on first use if they are not already cached.
"""

import json
import re
from pathlib import Path

import pytest

from core.graph.client import FalkorClient
from packs.oss.ecosystem import fetch, gaps, parse
from packs.oss.ecosystem import graph as G

TEST_GRAPH = "ecosystem_xz_test"
RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"
def _ecosystem_cache_missing() -> list[str]:
    """Cached records this module reads that are not on disk. data/raw is git-ignored."""
    names = json.loads((RESULTS / "ecosystem_sources.json").read_text(encoding="utf-8"))
    sources = names["sources"] + names.get("supplementary_sources", [])
    names = [Path(s["cache_file"]).name for s in sources]
    return [n for n in names if not (fetch.RAW_DIR / n).is_file()]


# Every test here reads data/raw/ecosystem. A clean clone has no such cache: skip, with the reason.
pytestmark = pytest.mark.skipif(
    bool(_ecosystem_cache_missing()),
    reason="data/raw/ecosystem is absent (git-ignored): run `make ecosystem-xz` to create it",
)
# Deliberately loose: anything shaped like local@host, even without a dot in the host.
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+")


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    c = FalkorClient()
    c.drop(TEST_GRAPH)
    yield c
    c.drop(TEST_GRAPH)


@pytest.fixture(scope="module")
def parsed():
    # data/raw is git-ignored: a clean clone has none. Skip, do not fetch from inside a test.
    # The tracked ecosystem_sources.json names every cached file the parser reads.
    names = json.loads((RESULTS / "ecosystem_sources.json").read_text(encoding="utf-8"))
    sources = names["sources"] + names.get("supplementary_sources", [])
    cached = [Path(s["cache_file"]).name for s in sources]
    gone = [n for n in cached if not (fetch.RAW_DIR / n).is_file()]
    if gone:
        pytest.skip(
            f"data/raw/ecosystem is absent (git-ignored, {len(gone)} files): "
            "run `make ecosystem-xz`"
        )
    events, _ = parse.all_events()
    return events, parse.build_registry(events)


@pytest.fixture(scope="module")
def loaded(client, parsed):
    events, reg = parsed
    G.load(client, events, reg, graph=TEST_GRAPH)
    return events, reg


def test_reload_gives_identical_counts(client, parsed, loaded):
    events, reg = parsed
    first = G.counts(client, TEST_GRAPH)
    G.load(client, events, reg, graph=TEST_GRAPH)
    second = G.counts(client, TEST_GRAPH)
    assert first["node_total"] > 0 and first["edge_total"] > 0
    assert second == first
    assert first["nodes"]["Place"] == 6
    assert first["nodes"]["Decision"] == 4
    assert first["nodes"]["Signal"] == len(events)


def _all_graph_strings(client) -> list[str]:
    out = []
    nodes = client.query(
        TEST_GRAPH, "MATCH (n) RETURN labels(n), properties(n)", timeout_ms=10_000
    ).result_set
    rels = client.query(
        TEST_GRAPH,
        "MATCH ()-[r]->() RETURN type(r), properties(r)",
        timeout_ms=10_000,
    ).result_set
    for row in nodes + rels:
        out.append(json.dumps(row, default=str))
    return out


def test_no_email_and_no_name_but_jia_tan(client, parsed, loaded):
    events, reg = parsed
    blob = "\n".join(_all_graph_strings(client))
    assert not EMAIL.search(blob), "an email-shaped string is in the graph"

    others = {n for n in reg.all_names if n != parse.PERSONA}
    assert others, "the parser saw no other names, so this check would prove nothing"
    low = blob.casefold()
    for name in others:
        assert name.casefold() not in low, "a person's name is in the graph"
    # Handles of everyone except the persona are identifiers too: they must be hashed.
    persona_handles = set()
    other_handles = set()
    for root, handles in reg.handles.items():
        bucket = persona_handles if parse.PERSONA in reg.names.get(root, set()) else other_handles
        bucket |= {h for _, h in handles}
    for h in other_handles - persona_handles:
        assert h.casefold() not in low, "a non-persona handle is in the graph"

    assert parse.PERSONA in blob  # the one allowed name is present
    assert "JiaT75" in blob and "jiatan" in blob  # its public handles


def test_output_files_carry_no_email_or_other_names(parsed):
    _, reg = parsed
    others = {n for n in reg.all_names if n != parse.PERSONA}
    for name in ("ecosystem_events.json", "ecosystem_gaps.json", "ecosystem_load.json"):
        path = RESULTS / name
        if not path.is_file():
            pytest.skip(f"{name} not generated yet; run `make ecosystem-xz`")
        text = path.read_text(encoding="utf-8")
        assert not EMAIL.search(text), name
        for n in others:
            assert n.casefold() not in text.casefold(), (name, "a person's name")


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)


def test_cache_holds_no_email():
    files = [f for f in fetch.RAW_DIR.iterdir() if not f.name.endswith(".meta.json")]
    assert files
    for f in files:
        text = f.read_text(encoding="utf-8")
        # JSON is checked on decoded strings: an escaped newline then an @mention is not an email.
        texts = list(_strings(json.loads(text))) if f.suffix == ".json" else [text]
        for t in texts:
            assert not EMAIL.search(t), f.name


def _cached_urls() -> set[str]:
    urls = set()
    for meta in fetch.RAW_DIR.glob("*.meta.json"):
        m = json.loads(meta.read_text(encoding="utf-8"))
        body = meta.with_name(meta.name.removesuffix(".meta.json"))
        if m["status"] == 200 and body.is_file():
            urls.add(m["url"])
    return urls


def test_each_gap_points_to_a_cached_source(client, parsed, loaded):
    events, reg = parsed
    result = gaps.run_all(client, events, reg, graph=TEST_GRAPH)
    cached = _cached_urls()
    rows = [g for d in result["decisions"] for g in d["gaps"]]
    assert rows, "no gap was computed"
    for g in rows:
        assert g["gap"] in {"UNREACHABLE", "UNNOTICED"}
        assert g["signal_source_url"] in cached, g["signal"]
        assert g["decision_source_url"] in cached, g["decision"]
    # The committed output must hold to the same rule.
    out = RESULTS / "ecosystem_gaps.json"
    if out.is_file():
        for d in json.loads(out.read_text(encoding="utf-8"))["decisions"]:
            for g in d["gaps"]:
                assert g["signal_source_url"] in cached
                assert g["decision_source_url"] in cached


def test_every_event_points_to_a_cached_source(parsed):
    events, reg = parsed
    cached = _cached_urls()
    for row in parse.event_rows(events, reg):
        assert row["source_url"] in cached, row["event_id"]


def test_decision_without_role_data_is_not_computed(client, parsed, loaded):
    events, reg = parsed
    client.query(TEST_GRAPH, "MATCH ()-[w:WATCHES]->() DELETE w", timeout_ms=10_000)
    try:
        result = gaps.run_all(client, events, reg, graph=TEST_GRAPH)
    finally:
        G.load(client, events, reg, graph=TEST_GRAPH)  # restore the edges
    assert result["decisions_computed"] == 0
    assert result["decisions_not_computed"] == 4
    assert all(d["gaps"] == [] and d["reason"] for d in result["decisions"])
