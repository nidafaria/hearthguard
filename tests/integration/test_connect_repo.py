"""Connect a public repo: the whole flow against the local HTTP stub and a real FalkorDB.

The stub (the `site` fixture, see conftest.py here) stands in for api.github.com. Requests
really travel over localhost. The graph is real FalkorDB, pinned 6.0.2. Nothing is mocked.

Expected values are worked by hand in the comments before each assertion.
"""

import json

import pytest

from core.graph.client import FalkorClient
from packs.oss import connect_repo as C
from packs.oss.xz_graph import scan_for_at_sign

FAST = {"min_interval_s": 0.0, "sleep": lambda s: None}


def commit(sha, when, login=None, email=None):
    author = {"name": "n", "date": when}
    if email:
        author["email"] = email
    c = {"sha": sha, "commit": {"author": author}}
    c["author"] = {"login": login} if login else None
    return c


def install_repo(site):
    base = site.base
    repo = "/repos/octo/demo"
    site.routes[repo] = (200, {}, json.dumps({"full_name": "octo/demo", "private": False}).encode())
    site.routes[f"{repo}/commits?per_page=100"] = (
        200,
        {"Link": f'<{base}{repo}/commits?per_page=100&page=2>; rel="next"'},
        json.dumps(
            [
                commit("a1", "2024-01-01T10:00:00Z", login="alice"),
                commit("b2", "2024-02-01T10:00:00Z", email="bob@example.com"),
            ]
        ).encode(),
    )
    site.routes[f"{repo}/commits?per_page=100&page=2"] = (
        200,
        {},
        json.dumps([commit("c3", "2024-03-01T10:00:00Z", login="alice")]).encode(),
    )
    site.routes[f"{repo}/releases?per_page=100"] = (
        200,
        {},
        json.dumps(
            [
                {
                    "tag_name": "v1.0",
                    "published_at": "2024-03-15T09:00:00Z",
                    "author": {"login": "alice"},
                }
            ]
        ).encode(),
    )
    site.routes["/repos/octo/missing"] = (404, {}, b'{"message":"Not Found"}')
    site.routes["/repos/octo/secret"] = (
        200,
        {},
        json.dumps({"full_name": "octo/secret", "private": True}).encode(),
    )


def fresh_client(graph):
    client = FalkorClient()
    client.drop(graph)
    return client


def test_parse_repo_accepts_owner_name_and_refuses_the_rest():
    assert C.parse_repo(" octocat/Hello-World ") == ("octocat", "Hello-World")
    for bad in ("octocat", "../etc", "a b/c", "octo/..", "", "-x/y/z"):
        with pytest.raises(C.RepoRefError):
            C.parse_repo(bad)


def test_connect_reads_the_stub_hashes_loads_and_computes_what_the_data_supports(
    site,
    tmp_path,
    monkeypatch,
):
    install_repo(site)
    monkeypatch.setenv("GITHUB_TOKEN", "tok_test_123_not_printed")
    graph = "org_octo_demo"
    client = fresh_client(graph)

    result = C.connect(
        "octo/demo", api=site.base, root=tmp_path, client=client, fetcher_kwargs=FAST
    )

    assert result["status"] == "DONE", result["reason"]
    # 3 commits over 2 pages, 1 release list, 1 repo read: 4 requests to the stub.
    assert result["requests"]["network"] == 4
    assert result["counts"]["commits_read"] == 3
    assert result["counts"]["actors"] == 2  # alice (login) and bob (email hashed), 2 distinct
    assert result["counts"]["releases_loaded"] == 1

    # Gaps: Jan 1 to Feb 1 is 31 days, Feb 1 to Mar 1 is 29 days; median of two is 30.
    assert result["metrics"]["cadence_days"]["status"] == "COMPUTED"
    assert result["metrics"]["cadence_days"]["value"] == pytest.approx(30.0)
    # Keepers in the 90 days up to T (Mar 15): alice and bob, both within 90 days.
    assert result["metrics"]["active_keepers"]["value"] == 2
    assert result["metrics"]["usual_path"]["value"] == "github-release"

    # A public history has no grant record, so these are NOT COMPUTED, with the reason.
    assert result["takeover_cost"]["status"] == "NOT COMPUTED"
    assert result["guardians"]["status"] == "NOT COMPUTED"
    assert result["best_hardening_step"]["status"] == "NOT COMPUTED"
    assert (
        "no CAN_GRANT" in result["takeover_cost"]["reason"]
        or "grant" in result["takeover_cost"]["reason"]
    )

    # The token is sent as a header to GitHub, and it never reaches the result or the cache.
    assert ("/repos/octo/demo", "Bearer tok_test_123_not_printed") in site.hits
    assert "tok_test_123_not_printed" not in json.dumps(result)
    cached = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert all(
        "tok_test_123_not_printed" not in p.read_text(encoding="utf-8", errors="ignore")
        for p in cached
    )

    # Identifiers are hashed: no '@' anywhere in the graph, and the email never appears.
    assert scan_for_at_sign(client, graph) == []
    counts = client.query(graph, "MATCH (a:Actor) RETURN count(a)").result_set[0][0]
    assert counts == 2

    # One step per name, every step done.
    assert [s["status"] for s in result["steps"]] == ["done"] * len(C.STEPS)


def test_a_second_run_over_the_same_cache_makes_no_network_request_and_adds_no_nodes(
    site,
    tmp_path,
):
    install_repo(site)
    graph = "org_octo_demo"
    client = fresh_client(graph)
    C.connect("octo/demo", api=site.base, root=tmp_path, client=client, fetcher_kwargs=FAST)
    nodes_after_first = client.query(graph, "MATCH (n) RETURN count(n)").result_set[0][0]

    again = C.connect("octo/demo", api=site.base, root=tmp_path, client=client, fetcher_kwargs=FAST)

    assert again["status"] == "DONE"
    assert again["requests"]["network"] == 0
    assert again["requests"]["from_cache"] == 4
    assert client.query(graph, "MATCH (n) RETURN count(n)").result_set[0][0] == nodes_after_first


def test_a_private_repo_is_refused_and_a_missing_one_is_not_found(site, tmp_path):
    install_repo(site)
    client = fresh_client("org_octo_secret")
    secret = C.connect(
        "octo/secret", api=site.base, root=tmp_path, client=client, fetcher_kwargs=FAST
    )
    assert secret["status"] == "REFUSED"
    assert "private" in secret["reason"]

    missing = C.connect(
        "octo/missing", api=site.base, root=tmp_path, client=client, fetcher_kwargs=FAST
    )
    assert missing["status"] == "NOT FOUND"
    assert missing["takeover_cost"]["status"] == "NOT COMPUTED"


def test_a_database_that_is_down_is_reported_at_the_step_it_stopped_on(site, tmp_path):
    install_repo(site)
    down = FalkorClient(host="127.0.0.1", port=1)  # nothing listens on port 1
    result = C.connect("octo/demo", api=site.base, root=tmp_path, client=down, fetcher_kwargs=FAST)
    assert result["status"] == "FAILED"
    failed = [s for s in result["steps"] if s["status"] == "failed"]
    assert failed and failed[0]["name"] == "load org graph"
    assert result["takeover_cost"]["status"] == "NOT COMPUTED"


def test_a_job_reports_its_steps_while_it_runs_and_its_result_at_the_end(site, tmp_path):
    install_repo(site)
    job_id = C.start_job(
        "octo/demo",
        api=site.base,
        root=tmp_path,
        client=fresh_client("org_octo_demo"),
        fetcher_kwargs=FAST,
    )
    import time

    for _ in range(600):
        job = C.get_job(job_id)
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done"
    assert job["result"]["status"] == "DONE"
    assert C.get_job("not-a-job") is None
