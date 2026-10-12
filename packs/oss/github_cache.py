"""Cache public GitHub data for tukaani-project/xz under data/raw/github/ (public data only, R6).

What is cached, each response as its own file with a `.meta.json` sidecar (source URL, fetch time):
  - the pull request list, all states, every page
  - for each pull request: its reviews, its review comments, its issue comments, every page
  - the commit history of MAINTAINERS and the CODEOWNERS locations, every page

Order of work: the PR list, then the file histories, then pull requests in ascending number, so
the most useful data arrives first if the rate limit slows the crawl.

The token is read from GITHUB_TOKEN in the environment or .env. It is sent as a header and is never
printed, logged, or written to a sidecar. Without a token GitHub allows 60 requests an hour, so the
crawl waits for resets; it resumes where it stopped, because anything already cached is skipped.
"""

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from packs.oss.raw_cache import Entry, Fetcher

OWNER, REPO = "tukaani-project", "xz"
API = "https://api.github.com"
REPO_API = f"{API}/repos/{OWNER}/{REPO}"
RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "github"
PER_PAGE = 100

# MAINTAINERS, and every place a CODEOWNERS file can live on GitHub.
HISTORY_PATHS = ("MAINTAINERS", "CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
PR_KINDS = (
    ("reviews", "pulls/{n}/reviews"),
    ("review_comments", "pulls/{n}/comments"),
    ("issue_comments", "issues/{n}/comments"),
)


def github_token() -> str | None:
    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    return token or None


def make_fetcher(root: Path = RAW_ROOT, **kwargs) -> Fetcher:
    token = github_token()
    return Fetcher(
        root,
        auth_header=f"Bearer {token}" if token else None,
        extra_headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        **kwargs,
    )


def safe(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", path)


@dataclass
class Request:
    """One request in the crawl: where it goes and the cache name it is stored under."""

    url: str
    name: str
    group: str  # pull_requests, reviews, review_comments, issue_comments, file_history
    entry: Entry | None = None  # the cached response, once there is one


def paged(
    fetcher: Fetcher, first_url: str, stem: str, group: str, fetch: bool
) -> Iterator[Request]:
    """Yield every page of a list. Pages come from the Link header of the page before.

    With fetch=False nothing is requested: the walk stops at the first page that is not cached,
    and that page is still yielded so the caller can count it as missing.
    """
    url, page = first_url, 1
    while url:
        name = f"{stem}_p{page:03d}.json"
        req = Request(url, name, group)
        entry = fetcher.get(url, name) if fetch else fetcher.cached(name)
        req.entry = entry
        yield req
        if entry is None:
            return
        url, page = entry.next_url(), page + 1


def pull_requests(fetcher: Fetcher, fetch: bool, repo_api: str = REPO_API) -> Iterator[Request]:
    url = f"{repo_api}/pulls?state=all&per_page={PER_PAGE}&sort=created&direction=asc"
    yield from paged(fetcher, url, "pulls_state-all", "pull_requests", fetch)


def file_histories(fetcher: Fetcher, fetch: bool, repo_api: str = REPO_API) -> Iterator[Request]:
    for path in HISTORY_PATHS:
        url = f"{repo_api}/commits?path={path}&per_page={PER_PAGE}"
        yield from paged(fetcher, url, f"commits_path-{safe(path)}", "file_history", fetch)


def pr_numbers(fetcher: Fetcher, repo_api: str = REPO_API) -> list[int]:
    """Numbers of the pull requests whose list pages are cached, ascending."""
    numbers: list[int] = []
    for req in pull_requests(fetcher, False, repo_api):
        if req.entry is not None and req.entry.body_path is not None:
            numbers += [pr["number"] for pr in req.entry.json()]
    return sorted(set(numbers))


def per_pr(
    fetcher: Fetcher, numbers: list[int], fetch: bool, repo_api: str = REPO_API
) -> Iterator[Request]:
    for n in numbers:
        for kind, route in PR_KINDS:
            url = f"{repo_api}/{route.format(n=n)}?per_page={PER_PAGE}"
            yield from paged(fetcher, url, f"pr-{n:05d}_{kind}", kind, fetch)


def crawl(fetcher: Fetcher, log=print, repo_api: str = REPO_API) -> dict:
    """Fetch everything not yet cached. Returns counts of requests made and skipped."""
    for _ in pull_requests(fetcher, True, repo_api):
        pass
    log(f"pull request list cached; {len(pr_numbers(fetcher, repo_api))} pull requests")
    for _ in file_histories(fetcher, True, repo_api):
        pass
    log("file histories cached")
    numbers = pr_numbers(fetcher, repo_api)
    for i, n in enumerate(numbers, start=1):
        for _ in per_pr(fetcher, [n], True, repo_api):
            pass
        if i % 5 == 0 or i == len(numbers):
            log(f"pull requests done: {i}/{len(numbers)}")
    return {"network_requests": fetcher.network_requests, "cache_hits": fetcher.cache_hits}


def missing(fetcher: Fetcher, repo_api: str = REPO_API) -> list[Request]:
    """Requests still to make, found without fetching. A lower bound: an uncached list page hides
    any pages after it."""
    todo: list[Request] = []
    walks = [pull_requests(fetcher, False, repo_api), file_histories(fetcher, False, repo_api)]
    walks.append(per_pr(fetcher, pr_numbers(fetcher, repo_api), False, repo_api))
    for walk in walks:
        todo += [r for r in walk if r.entry is None]
    return todo
