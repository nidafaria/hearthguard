"""Fetch public URLs once and keep them on disk with a record of where they came from.

Every response is saved under a root directory as `<name>` (the body) plus `<name>.meta.json`
(the sidecar: source URL, fetch time, status, and the few response headers that matter). A request
whose sidecar and body already exist is never repeated.

Rules this module enforces:
  - Requests are spaced out (`min_interval_s`) and carry an identifying User-Agent.
  - A GitHub-style rate limit is respected: when the remaining allowance is nearly used up, the
    fetcher sleeps until the reset time before the next request, and it waits and retries when the
    server answers 403 or 429 for a rate limit.
  - A secret (an Authorization header) is sent but never written to a sidecar, a body, or the log.
  - 404 is a real answer: it is cached as a sidecar with no body, so it is not asked again.
"""

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

USER_AGENT = "hearthguard-research-cache/0.1 (public data only; hackathon project)"
KEEP_HEADERS = (
    "etag",
    "link",
    "content-type",
    "last-modified",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-ratelimit-resource",
)
CACHEABLE_STATUS = (200, 404)


class FetchError(RuntimeError):
    """A request kept failing after retries."""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Entry:
    name: str
    status: int
    meta: dict
    body_path: Path | None
    from_cache: bool
    extra: dict = field(default_factory=dict)

    def text(self) -> str:
        return (
            self.body_path.read_text(encoding="utf-8", errors="replace") if self.body_path else ""
        )

    def json(self):
        return json.loads(self.body_path.read_text(encoding="utf-8")) if self.body_path else None

    def next_url(self) -> str | None:
        """The rel="next" URL from a stored Link header, if there is one."""
        link = self.meta.get("headers", {}).get("link")
        if not link:
            return None
        m = re.search(r'<([^>]+)>\s*;\s*rel="next"', link)
        return m.group(1) if m else None


class Fetcher:
    def __init__(
        self,
        root: Path,
        *,
        auth_header: str | None = None,
        min_interval_s: float = 1.0,
        rate_limit_reserve: int = 2,
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        log: Callable[[str], None] = print,
        extra_headers: dict | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._auth = auth_header
        self.min_interval_s = min_interval_s
        self.reserve = rate_limit_reserve
        self.max_attempts = max_attempts
        self._sleep = sleep
        self._now = now
        self._log = log
        self._extra = extra_headers or {}
        self._client = httpx.Client(timeout=timeout_s, follow_redirects=True)
        self._last_request = 0.0
        self._rate: tuple[int, int] | None = None  # (remaining, reset epoch) from the last reply
        self.network_requests = 0
        self.cache_hits = 0

    # ------------------------------------------------------------------ cache
    def paths(self, name: str) -> tuple[Path, Path]:
        return self.root / name, self.root / f"{name}.meta.json"

    def cached(self, name: str) -> Entry | None:
        body, meta_path = self.paths(name)
        if not meta_path.is_file():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") == 200 and not body.is_file():
            return None  # a sidecar without its body is incomplete
        self.cache_hits += 1
        return Entry(name, meta["status"], meta, body if body.is_file() else None, True)

    # ------------------------------------------------------------------ rate limit
    def _wait_for_allowance(self) -> None:
        if self._rate is not None and self._rate[0] <= self.reserve:
            wait = self._rate[1] - self._now() + 2
            if wait > 0:
                self._log(
                    f"rate limit nearly used up ({self._rate[0]} left); "
                    f"waiting {wait:.0f}s until it resets"
                )
                self._sleep(wait)
            self._rate = None
        gap = self.min_interval_s - (self._now() - self._last_request)
        if gap > 0:
            self._sleep(gap)

    def _note_rate(self, headers) -> None:
        remaining, reset = headers.get("x-ratelimit-remaining"), headers.get("x-ratelimit-reset")
        if remaining is not None and reset is not None:
            self._rate = (int(remaining), int(reset))

    # ------------------------------------------------------------------ fetching
    def get(self, url: str, name: str) -> Entry:
        hit = self.cached(name)
        if hit is not None:
            return hit

        headers = {"User-Agent": USER_AGENT, **self._extra}
        if self._auth:
            headers["Authorization"] = self._auth
        last = "no attempt"
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_allowance()
            self._last_request = self._now()
            self.network_requests += 1
            try:
                resp = self._client.get(url, headers=headers)
            except httpx.TransportError as e:
                last = f"transport error: {type(e).__name__}"
                self._sleep(min(2**attempt, 30))
                continue
            self._note_rate(resp.headers)

            if resp.status_code in CACHEABLE_STATUS:
                return self._store(url, name, resp)

            if resp.status_code in (403, 429):
                wait = self._rate_limit_wait(resp)
                last = f"HTTP {resp.status_code}, waiting {wait:.0f}s"
                self._log(f"{last} before retrying")
                self._sleep(wait)
                self._rate = None
                continue
            last = f"HTTP {resp.status_code}"
            self._sleep(min(2**attempt, 30))
        raise FetchError(f"{url} failed after {self.max_attempts} attempts ({last})")

    def _rate_limit_wait(self, resp) -> float:
        retry_after = resp.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            return float(retry_after) + 1
        if resp.headers.get("x-ratelimit-remaining") == "0" and resp.headers.get(
            "x-ratelimit-reset"
        ):
            return max(self._rate_reset_wait(resp), 1.0)
        return 60.0  # a secondary limit with no hint: wait a minute

    def _rate_reset_wait(self, resp) -> float:
        return int(resp.headers["x-ratelimit-reset"]) - self._now() + 2

    def _store(self, url: str, name: str, resp: httpx.Response) -> Entry:
        body_path, meta_path = self.paths(name)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "url": url,
            "fetched_at_utc": utc_now_iso(),
            "status": resp.status_code,
            "bytes": len(resp.content),
            "authenticated": bool(self._auth),  # whether a token was sent; never the token itself
            "headers": {k: resp.headers[k] for k in KEEP_HEADERS if k in resp.headers},
        }
        if resp.status_code == 200:
            tmp = body_path.with_name(body_path.name + ".tmp")
            tmp.write_bytes(resp.content)
            os.replace(tmp, body_path)
        tmp_meta = meta_path.with_name(meta_path.name + ".tmp")
        tmp_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_meta, meta_path)
        return Entry(
            name, resp.status_code, meta, body_path if resp.status_code == 200 else None, False
        )

    def close(self) -> None:
        self._client.close()
