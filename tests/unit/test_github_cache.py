"""The GitHub crawl against a local server: what it asks for, in what order, and what it skips."""

import json

from packs.oss import github_cache as gc
from packs.oss.raw_cache import Fetcher
from tests.unit.conftest import Clock

REPO = "/repos/o/r"
PULLS = f"{REPO}/pulls?state=all&per_page=100&sort=created&direction=asc"


def fetcher(tmp_path) -> Fetcher:
    clock = Clock()
    return Fetcher(tmp_path, min_interval_s=0, sleep=clock.sleep, now=clock.now, log=lambda _: None)


def json_ok(data, **headers):
    return 200, headers, json.dumps(data).encode()


def serve(site, prs_page1=(7, 3), prs_page2=(9,)):
    """A tiny repository: PR numbers split over two list pages, three comment kinds each."""
    page2_path = f"{REPO}/pulls?page=2"
    site.routes[PULLS] = json_ok(
        [{"number": n, "created_at": f"2022-0{n}-01T00:00:00Z"} for n in prs_page1],
        link=f'<{site.url(page2_path)}>; rel="next"',
    )
    site.routes[page2_path] = json_ok(
        [{"number": n, "created_at": f"2022-0{n}-01T00:00:00Z"} for n in prs_page2]
    )
    for n in (*prs_page1, *prs_page2):
        site.routes[f"{REPO}/pulls/{n}/reviews?per_page=100"] = json_ok(
            [{"submitted_at": f"2022-0{n}-02T00:00:00Z"}]
        )
        site.routes[f"{REPO}/pulls/{n}/comments?per_page=100"] = json_ok(
            [{"created_at": f"2022-0{n}-03T00:00:00Z"}, {"created_at": f"2022-0{n}-04T00:00:00Z"}]
        )
        site.routes[f"{REPO}/issues/{n}/comments?per_page=100"] = json_ok([])
    for path in gc.HISTORY_PATHS:
        body = (
            [{"commit": {"committer": {"date": "2021-05-05T00:00:00Z"}}}]
            if path == "MAINTAINERS"
            else []
        )
        site.routes[f"{REPO}/commits?path={path}&per_page=100"] = json_ok(body)
    return site.url(REPO)


def test_crawl_caches_everything_and_a_second_crawl_asks_for_nothing(site, tmp_path):
    api = serve(site)
    f = fetcher(tmp_path)
    gc.crawl(f, log=lambda _: None, repo_api=api)
    # 2 list pages + 4 file histories + 3 kinds for each of 3 pull requests
    assert len(site.hits) == 2 + 4 + 9
    assert gc.pr_numbers(f, api) == [3, 7, 9]
    assert gc.missing(f, api) == []

    again = fetcher(tmp_path)
    gc.crawl(again, log=lambda _: None, repo_api=api)
    assert len(site.hits) == 15 and again.network_requests == 0


def test_the_order_is_list_then_file_histories_then_pull_requests_ascending(site, tmp_path):
    api = serve(site)
    gc.crawl(fetcher(tmp_path), log=lambda _: None, repo_api=api)
    paths = [p for p, _ in site.hits]
    assert paths[0] == PULLS and paths[1].endswith("pulls?page=2")
    assert [p.split("path=")[1].split("&")[0] for p in paths[2:6]] == list(gc.HISTORY_PATHS)
    pr_order = [int(p.split("/")[5]) for p in paths[6:] if "/pulls/" in p or "/issues/" in p]
    assert pr_order == sorted(pr_order) and pr_order[0] == 3


def test_every_response_has_its_url_and_fetch_time_in_a_sidecar(site, tmp_path):
    api = serve(site)
    gc.crawl(fetcher(tmp_path), log=lambda _: None, repo_api=api)
    sidecars = list(tmp_path.glob("*.meta.json"))
    assert len(sidecars) == 15
    for path in sidecars:
        meta = json.loads(path.read_text(encoding="utf-8"))
        assert meta["url"].startswith(api) and meta["fetched_at_utc"].endswith("Z")
        assert (tmp_path / path.name.removesuffix(".meta.json")).is_file()


def test_missing_reports_exactly_what_was_deleted_and_a_rerun_fetches_only_that(site, tmp_path):
    api = serve(site)
    gc.crawl(fetcher(tmp_path), log=lambda _: None, repo_api=api)
    gone = tmp_path / "pr-00007_review_comments_p001.json"
    gone.unlink()
    f = fetcher(tmp_path)
    todo = gc.missing(f, api)
    assert [(r.group, r.name) for r in todo] == [("review_comments", gone.name)]
    before = len(site.hits)
    gc.crawl(f, log=lambda _: None, repo_api=api)
    assert len(site.hits) == before + 1 and gone.is_file()


def test_missing_before_any_crawl_is_only_the_first_page_of_the_list(site, tmp_path):
    api = serve(site)
    todo = gc.missing(fetcher(tmp_path), api)
    # Nothing is cached, so the walk cannot see past the first list page or any pull request.
    assert [r.group for r in todo] == ["pull_requests", "file_history"] + ["file_history"] * 3
    assert len(site.hits) == 0  # finding out what is missing fetches nothing


def test_pull_requests_of_every_state_are_requested(site, tmp_path):
    api = serve(site)
    gc.crawl(fetcher(tmp_path), log=lambda _: None, repo_api=api)
    assert "state=all" in site.hits[0][0]


def test_codeowners_is_checked_in_every_place_github_reads_it():
    assert set(gc.HISTORY_PATHS) == {
        "MAINTAINERS",
        "CODEOWNERS",
        ".github/CODEOWNERS",
        "docs/CODEOWNERS",
    }
    assert gc.safe(".github/CODEOWNERS") == ".github__CODEOWNERS"


def test_an_empty_token_means_no_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "   ")
    assert gc.github_token() is None
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    assert gc.github_token() == "abc"
