"""The inventory describes the cache with counts and dates only, and says when it is incomplete."""

import json

from packs.oss import github_cache as gc
from packs.oss import mail_cache as mc
from packs.oss import raw_inventory as inv
from packs.oss.raw_cache import Fetcher
from tests.unit.conftest import Clock, needs_salt
from tests.unit.test_github_cache import serve
from tests.unit.test_mail_cache import archive


def fetcher(root) -> Fetcher:
    clock = Clock()
    return Fetcher(root, min_interval_s=0, sleep=clock.sleep, now=clock.now, log=lambda _: None)


def github_cache_of_three_prs(site, root):
    api = serve(site)
    gc.crawl(fetcher(root), log=lambda _: None, repo_api=api)


def test_github_counts_and_date_ranges_match_what_was_served(site, tmp_path):
    github_cache_of_three_prs(site, tmp_path)
    g = inv.github_inventory(tmp_path)
    s = g["sources"]
    # 3 PRs (numbers 3, 7, 9), created 2022-03-01, 2022-07-01, 2022-09-01, over 2 list pages.
    assert (s["pull_requests"]["responses"], s["pull_requests"]["items"]) == (2, 3)
    assert s["pull_requests"]["earliest"] == "2022-03-01T00:00:00Z"
    assert s["pull_requests"]["latest"] == "2022-09-01T00:00:00Z"
    assert (s["reviews"]["responses"], s["reviews"]["items"]) == (3, 3)
    assert s["reviews"]["earliest"] == "2022-03-02T00:00:00Z"
    assert (s["review_comments"]["responses"], s["review_comments"]["items"]) == (3, 6)
    assert s["review_comments"]["latest"] == "2022-09-04T00:00:00Z"
    assert (s["issue_comments"]["responses"], s["issue_comments"]["items"]) == (3, 0)
    assert s["issue_comments"]["earliest"] is None  # an empty list has no dates; none is invented
    assert (s["file_history"]["responses"], s["file_history"]["items"]) == (4, 1)
    assert s["file_history"]["earliest"] == s["file_history"]["latest"] == "2021-05-05T00:00:00Z"
    for source in s.values():
        assert source["fetched_first_utc"].endswith("Z") and source["fetched_last_utc"].endswith(
            "Z"
        )
        assert source["responses_with_token"] == 0
    assert g["complete"] is True and g["requests_still_missing_at_least"] == 0


def test_the_inventory_says_so_when_the_github_crawl_is_incomplete(site, tmp_path):
    github_cache_of_three_prs(site, tmp_path)
    (tmp_path / "pr-00009_reviews_p001.json").unlink()
    (tmp_path / "pr-00003_issue_comments_p001.json.meta.json").unlink()
    g = inv.github_inventory(tmp_path)
    assert g["complete"] is False and g["requests_still_missing_at_least"] == 2


def test_an_empty_cache_is_not_complete(tmp_path):
    g = inv.github_inventory(tmp_path)
    assert g["complete"] is False
    assert g["sources"]["pull_requests"]["responses"] == 0
    assert g["sources"]["pull_requests"]["earliest"] is None


@needs_salt
def test_mail_counts_only_messages_in_scope_and_dates_them(site, monkeypatch, tmp_path):
    dates = archive(site, monkeypatch)
    mc.cache_messages(fetcher(tmp_path), log=lambda _: None)
    m = inv.mail_inventory(tmp_path)
    in_window = sorted(
        d for i, d in dates.items() if mc.WINDOW_START <= d < mc.WINDOW_END and i != 20
    )
    assert m["messages_in_scope"] == len(in_window)
    assert m["earliest"] == in_window[0].isoformat().replace("+00:00", "Z")
    assert m["latest"] == in_window[-1].isoformat().replace("+00:00", "Z")
    assert m["newest_message_number"] == 40
    assert m["message_numbers_not_found_below_newest"] >= 1  # message 20 is missing
    assert m["messages_cached_total"] >= m["messages_in_scope"]  # the search probes are cached too
    assert m["fetched_first_utc"].endswith("Z") and m["fetched_last_utc"].endswith("Z")


@needs_salt
def test_the_inventory_text_has_no_name_email_subject_or_url(site, monkeypatch, tmp_path):
    github_cache_of_three_prs(site, tmp_path / "gh")
    archive(site, monkeypatch)
    mc.cache_messages(fetcher(tmp_path / "mail"), log=lambda _: None)
    text = json.dumps(
        {
            "github": inv.github_inventory(tmp_path / "gh"),
            "mail": inv.mail_inventory(tmp_path / "mail"),
        }
    )
    assert "@" not in text
    assert "http" not in text
    assert "Sender" not in text and "topic" not in text
    assert "127.0.0.1" not in text
