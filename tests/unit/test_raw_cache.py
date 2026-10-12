"""The fetch-and-cache layer: sidecars, skipping, rate limits, and no token in any file."""

import re

import pytest

from packs.oss.raw_cache import Fetcher, FetchError
from tests.unit.conftest import Clock

ISO_Z = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def make(tmp_path, clock=None, logs=None, **kw) -> Fetcher:
    clock = clock or Clock()
    kw.setdefault("min_interval_s", 0)
    return Fetcher(
        tmp_path,
        sleep=clock.sleep,
        now=clock.now,
        log=(logs if logs is not None else []).append,
        **kw,
    )


def ok(body=b'{"x": 1}', **headers):
    return (200, headers, body)


def test_response_is_saved_with_source_url_and_fetch_time(site, tmp_path):
    site.routes["/a"] = ok()
    entry = make(tmp_path).get(site.url("/a"), "a.json")
    assert entry.body_path.read_bytes() == b'{"x": 1}'
    meta = entry.meta
    assert meta["url"] == site.url("/a")
    assert ISO_Z.match(meta["fetched_at_utc"])
    assert meta["status"] == 200 and meta["bytes"] == 8
    assert (tmp_path / "a.json.meta.json").is_file()


def test_something_already_cached_is_not_requested_again(site, tmp_path):
    site.routes["/a"] = ok()
    f = make(tmp_path)
    first = f.get(site.url("/a"), "a.json")
    second = f.get(site.url("/a"), "a.json")
    assert (first.from_cache, second.from_cache) == (False, True)
    assert site.count("/a") == 1
    # A new Fetcher on the same folder (a later run) also skips it.
    make(tmp_path).get(site.url("/a"), "a.json")
    assert site.count("/a") == 1


def test_a_sidecar_without_its_body_is_fetched_again(site, tmp_path):
    site.routes["/a"] = ok()
    f = make(tmp_path)
    f.get(site.url("/a"), "a.json")
    (tmp_path / "a.json").unlink()
    f.get(site.url("/a"), "a.json")
    assert site.count("/a") == 2


def test_a_404_is_cached_without_a_body_and_not_asked_again(site, tmp_path):
    f = make(tmp_path)
    entry = f.get(site.url("/gone"), "gone.json")
    assert entry.status == 404 and entry.body_path is None
    assert not (tmp_path / "gone.json").exists()
    assert entry.meta["status"] == 404
    f.get(site.url("/gone"), "gone.json")
    assert site.count("/gone") == 1


def test_the_token_is_sent_but_never_written_or_logged(site, tmp_path):
    site.routes["/a"] = ok(b'{"ok": true}')
    logs: list[str] = []
    f = make(tmp_path, logs=logs, auth_header="Bearer SECRET-TOKEN-123")
    f.get(site.url("/a"), "a.json")
    assert site.hits[0][1] == "Bearer SECRET-TOKEN-123"  # it really was sent
    everything = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())
    assert "SECRET-TOKEN-123" not in everything
    assert "SECRET-TOKEN-123" not in "\n".join(logs)
    assert f.cached("a.json").meta["authenticated"] is True


def test_unauthenticated_responses_are_marked_so(site, tmp_path):
    site.routes["/a"] = ok()
    assert make(tmp_path).get(site.url("/a"), "a.json").meta["authenticated"] is False
    assert site.hits[0][1] is None


def test_it_waits_for_the_reset_when_the_allowance_is_nearly_used_up(site, tmp_path):
    clock, logs = Clock(), []
    reset = int(clock.now()) + 100
    site.routes["/a"] = ok(**{"x-ratelimit-remaining": "1", "x-ratelimit-reset": str(reset)})
    site.routes["/b"] = ok()
    site.routes["/c"] = ok()
    f = make(tmp_path, clock, logs)
    f.get(site.url("/a"), "a.json")
    assert clock.sleeps == []  # nothing to wait for before the first request
    f.get(site.url("/b"), "b.json")
    assert len(clock.sleeps) == 1 and 100 <= clock.sleeps[0] <= 103
    assert any("rate limit" in line and "waiting" in line for line in logs)
    f.get(site.url("/c"), "c.json")
    assert len(clock.sleeps) == 1  # the allowance reset, so no second wait


def test_it_does_not_wait_while_plenty_is_left(site, tmp_path):
    clock = Clock()
    site.routes["/a"] = ok(**{"x-ratelimit-remaining": "50", "x-ratelimit-reset": "9999999999"})
    site.routes["/b"] = ok()
    f = make(tmp_path, clock)
    f.get(site.url("/a"), "a.json")
    f.get(site.url("/b"), "b.json")
    assert clock.sleeps == []


def test_a_rate_limit_error_waits_for_the_reset_then_retries(site, tmp_path):
    clock = Clock()
    reset = int(clock.now()) + 30

    def route(call):
        if call == 1:
            return 403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}, b"limit"
        return ok(b'{"after": "wait"}')

    site.routes["/a"] = route
    entry = make(tmp_path, clock).get(site.url("/a"), "a.json")
    assert entry.status == 200 and entry.json() == {"after": "wait"}
    assert site.count("/a") == 2
    assert any(30 <= s <= 33 for s in clock.sleeps)


def test_retry_after_is_honoured(site, tmp_path):
    clock = Clock()
    site.routes["/a"] = lambda call: (429, {"retry-after": "7"}, b"slow") if call == 1 else ok()
    make(tmp_path, clock).get(site.url("/a"), "a.json")
    assert any(7 <= s <= 9 for s in clock.sleeps)


def test_it_gives_up_after_the_attempt_limit_and_caches_nothing(site, tmp_path):
    site.routes["/a"] = (500, {}, b"broken")
    f = make(tmp_path, max_attempts=3)
    with pytest.raises(FetchError, match="3 attempts"):
        f.get(site.url("/a"), "a.json")
    assert site.count("/a") == 3
    assert not (tmp_path / "a.json.meta.json").exists()


def test_requests_are_spaced_by_the_minimum_interval(site, tmp_path):
    clock = Clock()
    site.routes["/a"] = ok()
    site.routes["/b"] = ok()
    f = make(tmp_path, clock, min_interval_s=1.0)
    f.get(site.url("/a"), "a.json")
    f.get(site.url("/b"), "b.json")
    assert clock.sleeps and 0.9 <= clock.sleeps[-1] <= 1.0


def test_next_page_comes_from_the_stored_link_header(site, tmp_path):
    link = '<http://example.test/p2>; rel="next", <http://example.test/p9>; rel="last"'
    site.routes["/a"] = ok(b"[]", link=link)
    site.routes["/b"] = ok(b"[]")
    f = make(tmp_path)
    assert f.get(site.url("/a"), "a.json").next_url() == "http://example.test/p2"
    assert f.get(site.url("/b"), "b.json").next_url() is None
