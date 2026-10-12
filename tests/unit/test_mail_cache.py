"""The mailing-list cache: parsing, hashing the author, finding the date range, and the index."""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from core.graph.hashing import MissingSaltError, identifier_hash, load_salt
from packs.oss import mail_cache as mc
from packs.oss.raw_cache import Fetcher
from tests.unit.conftest import Clock

LIST_PATH = "/list/"


def page(n: int, date: datetime, name="Pat Example", subject="[xz-devel] A topic", email=None):
    """A message page shaped like the archive's, with a body that quotes an address."""
    mailto = f'<a href="mailto:{email}">mail</a>' if email else ""
    return f"""<html><head><title>{subject}</title></head><body>
<div class="msgHead"><h1><span class="subject"><a href="/s">
<span itemprop="name">{subject}</span></a></span></h1>
<p><span class="sender pipe"><a href="/s"><span itemprop="author">
<span itemprop="name">{name}</span></span></a></span>
{mailto}<span class="date"><a href="/d">{format_datetime(date)}</a></span></p></div>
<div itemprop="articleBody">On someone wrote: contact quoted.address@example.org for details.</div>
</body></html>""".encode()


def fetcher(tmp_path) -> Fetcher:
    clock = Clock()
    return Fetcher(tmp_path, min_interval_s=0, sleep=clock.sleep, now=clock.now, log=lambda _: None)


# ------------------------------------------------------------------ parsing
def test_parse_reads_subject_sender_and_date_in_utc():
    html = page(
        1, datetime(2022, 5, 19, 20, 41, 31, tzinfo=UTC), "Pat Example", "Re: [xz-devel] Hi"
    )
    parsed = mc.parse_message(html.decode())
    assert parsed["subject"] == "Re: [xz-devel] Hi"
    assert parsed["sender_name"] == "Pat Example"
    assert parsed["date"] == datetime(2022, 5, 19, 20, 41, 31, tzinfo=UTC)


def test_the_real_archive_date_format_converts_to_utc():
    html = (
        '<div class="msgHead"><span class="date">'
        "<a>Thu, 19 May 2022 13:41:31 -0700</a></span></div>"
    )
    assert mc.parse_message(html)["date"] == datetime(2022, 5, 19, 20, 41, 31, tzinfo=UTC)


def test_a_page_without_a_date_parses_to_none_not_a_guess():
    assert mc.parse_message("<html>nothing here</html>")["date"] is None


def test_an_address_in_the_body_is_not_taken_as_the_author():
    parsed = mc.parse_message(page(1, datetime(2022, 1, 1, tzinfo=UTC)).decode())
    assert parsed["sender_email"] is None


# ------------------------------------------------------------------ hashing
def _salt_is_set() -> bool:
    try:
        load_salt()
    except MissingSaltError:
        return False
    return True


# .env is git-ignored, so a clean clone has no salt. These tests need it; they skip without it.
needs_salt = pytest.mark.skipif(
    not _salt_is_set(),
    reason="HEARTHGUARD_HASH_SALT is not set (.env is git-ignored): add it to run hashing tests",
)


@needs_salt
def test_an_email_is_hashed_when_the_header_shows_one():
    html = page(1, datetime(2022, 1, 1, tzinfo=UTC), email="Pat@Example.org").decode()
    parsed = mc.parse_message(html)
    h, basis = mc.author_hash(parsed["sender_email"], parsed["sender_name"])
    assert basis == "email" and h == identifier_hash("pat@example.org")


@needs_salt
def test_a_display_name_is_hashed_when_there_is_no_email_and_in_its_own_namespace():
    h, basis = mc.author_hash(None, "Pat Example")
    assert basis == "display_name" and len(h) == 64
    assert h == mc.author_hash(None, " pat example ")[0]  # case and spaces do not matter
    assert h != identifier_hash("pat example")  # a name hash is not an email hash
    assert mc.author_hash(None, None) == (None, None)


# ------------------------------------------------------------------ the archive and its range
def archive(site, monkeypatch, n_messages=40, missing=(20,), step_days=60):
    """Messages 1..n, 60 days apart from 2019-06-01 (so 2021 to 2024 falls in the middle)."""
    monkeypatch.setattr(mc, "BASE", site.url(LIST_PATH))
    start = datetime(2019, 6, 1, tzinfo=UTC)
    dates = {i: start + timedelta(days=step_days * i) for i in range(1, n_messages + 1)}
    for i, d in dates.items():
        if i not in missing:
            site.routes[f"{LIST_PATH}{mc.msg_name(i)}"] = (
                200,
                {},
                page(i, d, name=f"Sender {i % 3}", subject=f"[xz-devel] topic {i}"),
            )
    return dates


def expected_window(dates, missing=(20,)):
    inside = [
        i for i, d in dates.items() if mc.WINDOW_START <= d < mc.WINDOW_END and i not in missing
    ]
    return min(inside), max(inside)


def test_the_range_search_finds_the_window_without_fetching_everything(site, monkeypatch, tmp_path):
    # 400 messages, 6 days apart from mid-2019, so the 2021 to 2024 window is in the middle.
    dates = archive(site, monkeypatch, n_messages=400, missing=(), step_days=6)
    f = fetcher(tmp_path)
    first, last, top = mc.plan_range(f)
    lo, hi = expected_window(dates, missing=())
    assert top == 400
    assert (first, last) == (lo, hi)
    print(f"[search] archive of 400 messages, {f.network_requests} requests to find the window")
    assert f.network_requests < 100  # a search, not a scan of all 400


def test_everything_in_the_window_and_the_named_messages_are_cached(site, monkeypatch, tmp_path):
    dates = archive(site, monkeypatch)
    f = fetcher(tmp_path)
    summary = mc.cache_messages(f, log=lambda _: None)
    lo, hi = expected_window(dates)
    assert (summary["first"], summary["last"], summary["top"]) == (lo, hi, 40)
    cached_ok = {int(p.name[3:8]) for p in tmp_path.glob("msg*.html") if p.suffix == ".html"}
    in_window = {i for i in range(lo, hi + 1) if i != 20}
    assert in_window <= cached_ok
    assert 512 in {
        int(p.name[3:8]) for p in tmp_path.glob("msg*.html.meta.json")
    }  # named, asked for


def test_a_missing_message_inside_the_window_is_recorded_not_fatal(site, monkeypatch, tmp_path):
    archive(site, monkeypatch)
    mc.cache_messages(fetcher(tmp_path), log=lambda _: None)
    meta = json.loads((tmp_path / "msg00020.html.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == 404 and not (tmp_path / "msg00020.html").exists()


def test_a_second_run_asks_for_nothing(site, monkeypatch, tmp_path):
    archive(site, monkeypatch)
    mc.cache_messages(fetcher(tmp_path), log=lambda _: None)
    hits = len(site.hits)
    again = fetcher(tmp_path)
    mc.cache_messages(again, log=lambda _: None)
    assert len(site.hits) == hits and again.network_requests == 0


# ------------------------------------------------------------------ the index
def test_the_index_holds_no_name_no_email_and_no_address(site, monkeypatch, tmp_path):
    archive(site, monkeypatch)
    mc.cache_messages(fetcher(tmp_path), log=lambda _: None)
    out = mc.write_index(tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "@" not in text
    assert "Sender" not in text and "quoted.address" not in text
    rows = json.loads(text)["messages"]
    found = [r for r in rows if r["status"] == 200]
    assert found and all(r["author_hash"] and len(r["author_hash"]) == 64 for r in found)
    assert {r["author_hash_basis"] for r in found} == {"display_name"}
    # Three different display names make three different hashes, and the same name the same hash.
    assert len({r["author_hash"] for r in found}) == 3
    assert all(r["date_utc"].endswith("Z") for r in found)


def test_in_scope_covers_the_window_and_the_named_range():
    d_in, d_out = datetime(2022, 1, 1, tzinfo=UTC), datetime(2018, 1, 1, tzinfo=UTC)
    assert mc.in_scope(5, d_in) and not mc.in_scope(5, d_out) and not mc.in_scope(5, None)
    assert mc.in_scope(512, d_out) and mc.in_scope(571, None)
    assert not mc.in_scope(572, d_out)
    assert mc.in_scope(5, datetime(2024, 12, 31, 23, 59, tzinfo=UTC))
    assert not mc.in_scope(5, datetime(2025, 1, 1, tzinfo=UTC))


def test_message_pages_are_named_by_number():
    assert mc.msg_name(563) == "msg00563.html"
    assert mc.msg_name(5) == "msg00005.html"
    assert mc.msg_url(563).endswith("/msg00563.html")


@pytest.mark.parametrize("n", [512, 563, 571])
def test_the_messages_the_spec_names_are_in_the_explicit_range(n):
    assert n in mc.EXPLICIT
    assert 511 not in mc.EXPLICIT and 572 not in mc.EXPLICIT
