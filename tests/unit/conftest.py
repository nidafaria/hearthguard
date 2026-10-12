"""A small real HTTP server on localhost for the cache tests. No mocks: requests really travel."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core.graph.hashing import MissingSaltError, load_salt


class Site:
    """Routes map a path (with its query string) to (status, headers, body) or to a function of
    the call number that returns one. Unknown paths answer 404."""

    def __init__(self) -> None:
        self.routes: dict = {}
        self.hits: list[tuple[str, str | None]] = []  # (path, Authorization header)
        self.posts: list = []  # JSON bodies of POST requests
        self.base = ""

    def url(self, path: str) -> str:
        return self.base + path

    def count(self, path: str) -> int:
        return sum(1 for p, _ in self.hits if p == path)


@pytest.fixture
def site():
    site = Site()

    class Handler(BaseHTTPRequestHandler):
        def _serve(self):
            site.hits.append((self.path, self.headers.get("Authorization")))
            route = site.routes.get(self.path)
            if callable(route):
                route = route(site.count(self.path))
            status, headers, body = route if route else (404, {}, b"not found")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._serve()

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            site.posts.append(json.loads(raw) if raw else None)  # the request bodies, in order
            self._serve()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    site.base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    yield site
    server.shutdown()
    server.server_close()


class Clock:
    """A fake clock: sleeping advances it instantly, so rate-limit waits cost no real time."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


def salt_is_set() -> bool:
    try:
        load_salt()
    except MissingSaltError:
        return False
    return True


# .env is git-ignored, so a clean clone has no salt. Tests that hash identifiers need it.
# They skip, with this reason, when it is absent.
needs_salt = pytest.mark.skipif(
    not salt_is_set(),
    reason="HEARTHGUARD_HASH_SALT is not set (.env is git-ignored): add it to run hashing tests",
)
