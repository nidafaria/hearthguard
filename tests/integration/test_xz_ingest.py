"""xz git ingest into a scratch org graph, with the real public mirror and a real FalkorDB."""

import statistics

import pytest

from core.graph.client import FalkorClient
from core.normal import metrics
from eval.xz_normal import QUARTER_ENDS, end_of_day_utc
from packs.oss import git_ingest, xz_graph

TEST_ORG = "xz_test"  # metrics read org_<id>, so this scratch org lives in graph org_xz_test
TEST_GRAPH = f"org_{TEST_ORG}"
D = 86_400


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture(scope="module")
def parsed():
    git_ingest.ensure_mirror()
    mirror = git_ingest.RAW_DIR / "xz.git"
    tags = git_ingest.read_tags(mirror)
    commits = git_ingest.read_commits(mirror, {t["target_sha"] for t in tags})
    names = [t["name"] for t in tags if t["kind"] == "annotated"]
    return commits, tags, git_ingest.verify_tags(mirror, names)


@pytest.fixture(scope="module")
def loaded(client, parsed):
    commits, tags, sigs = parsed
    client.drop(TEST_GRAPH)
    xz_graph.load(client, commits, tags, sigs, graph=TEST_GRAPH)
    yield xz_graph.graph_counts(client, TEST_GRAPH)
    client.drop(TEST_GRAPH)


def test_ingest_twice_gives_identical_counts(client, parsed, loaded):
    commits, tags, sigs = parsed
    first = loaded
    xz_graph.load(client, commits, tags, sigs, graph=TEST_GRAPH)
    second = xz_graph.graph_counts(client, TEST_GRAPH)
    print(f"\n[ingest] run 1: {first}\n[ingest] run 2: {second}")
    assert second == first
    assert first["nodes"]["Action"] == len(commits) + sum(t["kind"] == "annotated" for t in tags)
    assert first["nodes"]["Actor"] == len({c["hid"] for c in commits})


def test_no_raw_email_in_graph_or_parsed_records(client, parsed, loaded):
    commits, tags, _ = parsed
    assert xz_graph.scan_for_at_sign(client, TEST_GRAPH) == []
    assert not any("@" in str(c) for c in commits)
    assert not any("@" in str(t) for t in tags)


def test_actors_hold_only_hashes_and_the_public_persona_handle(client, loaded):
    rows = client.query(TEST_GRAPH, "MATCH (a:Actor) RETURN a").result_set
    allowed = {"hid", "kind", "first_seen_in_org", "handle_public"}
    handles = set()
    for (actor,) in rows:
        assert set(actor.properties) <= allowed
        assert len(actor.properties["hid"]) == 64
        if "handle_public" in actor.properties:
            handles.add(actor.properties["handle_public"])
    assert handles == {"JiaT75"}


def test_no_grants_or_privileges_are_invented(loaded):
    assert "Privilege" not in loaded["nodes"]
    assert set(loaded["edges"]) <= {"DID", "VIA", "OF"}
    assert "Flow" not in loaded["nodes"]  # no OUTSIDER / guardians projection in this step


def test_releases_use_the_git_path_and_are_unverified_without_keys(client, loaded):
    rows = client.query(
        TEST_GRAPH,
        "MATCH (r:Action {kind: 'release'})-[:VIA]->(p:Path) "
        "RETURN p.channel, p.verified, count(r)",
    ).result_set
    assert rows == [["git", False, loaded["edges"]["VIA"]]]


def test_graph_metrics_match_an_independent_python_computation(client, parsed, loaded):
    commits, tags, _ = parsed
    releases = [t for t in tags if t["kind"] == "annotated"]
    for quarter, d in QUARTER_ENDS:
        T = end_of_day_utc(d)
        window = sorted(c["at"] for c in commits if T - 730 * D < c["at"] <= T)
        gaps = [b - a for a, b in zip(window, window[1:], strict=False)]
        cadence = metrics.commit_cadence_days(client, TEST_ORG, T)
        assert cadence.value == pytest.approx(statistics.median(gaps) / D, rel=1e-9), quarter
        keepers = {c["hid"] for c in commits if T - 90 * D < c["at"] <= T}
        assert metrics.active_keepers_as_of_T(client, TEST_ORG, T).value == len(keepers), quarter
        in_window = [r for r in releases if T - 730 * D < r["at"] <= T]
        channel = metrics.release_channel_as_of_T(client, TEST_ORG, T)
        assert (channel.value == "git") == bool(in_window), quarter
