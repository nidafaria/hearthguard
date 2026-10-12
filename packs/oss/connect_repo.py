"""Connect a public GitHub repository (owner/name): read-only, cached, hashed, one org graph.

Read-only: every request is a GET. The token (GITHUB_TOKEN, from the environment or .env) is sent as
a header. It is never printed, logged or written to a file, and there is no login flow.
Cache: every response goes to data/raw/connect/<owner>__<name>/ with its URL and fetch time.
Hashing: a commit author or release tagger is identified by GitHub login when there is one, else by
email. Only the salted HMAC (core/graph/hashing.py) reaches the graph. Raw emails stay in the cache.
Graph: org_<id> with the §6.1 Org, Actor, Action and DID shape, connected_by 'public_record' (§4.5).
Not computed: takeover cost, guardians and the hardening step need a privilege grant record.
A public commit history has none, so they are reported NOT COMPUTED with the reason.
Nothing is guessed.

Run as a job (what the UI does): start_job(repo) returns an id; get_job(id) returns live progress.
"""

import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.graph.client import FalkorClient
from core.graph.hashing import identifier_hash, load_salt
from core.graph.schema import apply_schema
from core.normal import metrics as M
from core.takeover.cost import takeover_cost
from core.takeover.guardians import guardians
from packs.oss.github_cache import github_token
from packs.oss.raw_cache import Fetcher, FetchError

GITHUB_API = "https://api.github.com"
RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "connect"
PER_PAGE = 100
MAX_COMMIT_PAGES = 3  # 300 commits at most: the connect flow reads recent history, not all of it
PRIVILEGE = "release"  # the privilege the takeover question asks about (spec §2.2)
NOT_COMPUTED = "NOT COMPUTED"
WRITE_TIMEOUT_MS = 60_000
LABEL = "Public record: GitHub read-only GET requests. Identifiers hashed on ingest."
NO_GRANTS = (
    "a public commit and release history records no privilege grant, so takeover cost has no "
    "CAN_GRANT or Privilege data to read"
)

REPO_RE = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})$")


class RepoRefError(ValueError):
    """The text is not owner/name."""


def parse_repo(text: str) -> tuple[str, str]:
    m = REPO_RE.match((text or "").strip())
    if not m or m.group(2) in (".", ".."):
        raise RepoRefError("expected owner/name, for example octocat/Hello-World")
    return m.group(1), m.group(2)


def graph_id(owner: str, name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", f"{owner}_{name}".lower()).strip("_")


def utc_iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_of(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


@dataclass
class Step:
    name: str
    status: str = "waiting"  # waiting, running, done, failed
    detail: str | None = None


@dataclass
class Progress:
    """The steps of one run, in order. Read by the UI while the run is going."""

    steps: list[Step] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def plan(self, names: list[str]) -> None:
        with self._lock:
            self.steps = [Step(n) for n in names]

    def set(self, name: str, status: str, detail: str | None = None) -> None:
        with self._lock:
            for s in self.steps:
                if s.name == name:
                    s.status, s.detail = status, detail
                    return
            self.steps.append(Step(name, status, detail))

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [asdict(s) for s in self.steps]


STEPS = [
    "read repository",
    "read commit history",
    "read releases",
    "load org graph",
    "normal metrics",
    "takeover cost",
    "guardians",
    "hardening step",
]


def _metric(res: M.MetricResult) -> dict:
    return {
        "status": res.status,
        "value": res.value,
        "unit": res.unit,
        "n": res.n,
        "reason": res.reason,
    }


def _not_computed(reason: str) -> dict:
    return {"status": NOT_COMPUTED, "value": None, "reason": reason}


def _commit_rows(commits: list[dict], salt: bytes) -> tuple[list[dict], int]:
    rows, skipped = [], 0
    for c in commits:
        meta = c.get("commit") or {}
        author = meta.get("author") or {}
        login = ((c.get("author") or {}).get("login") or "").lower()
        email = (author.get("email") or "").lower()
        if login:
            ident = f"login:{login}"
        elif email:
            ident = f"email:{email}"
        else:
            skipped += 1
            continue
        when = author.get("date") or (meta.get("committer") or {}).get("date")
        if not when:
            skipped += 1
            continue
        rows.append(
            {
                "hid": identifier_hash(ident, salt=salt),
                "sha": c["sha"],
                "at": epoch_of(when),
            }
        )
    return rows, skipped


def _release_rows(releases: list[dict], salt: bytes) -> list[dict]:
    rows = []
    for r in releases:
        when = r.get("published_at") or r.get("created_at")
        if not when:
            continue
        login = ((r.get("author") or {}).get("login") or "").lower()
        rows.append(
            {
                "name": r.get("tag_name") or str(r.get("id")),
                "at": epoch_of(when),
                "hid": identifier_hash(f"login:{login}", salt=salt) if login else None,
            }
        )
    return rows


def load_graph(
    client: FalkorClient, graph: str, org_id: str, commits: list[dict], releases: list[dict]
):
    """MERGE on unique keys: a second load over the same records changes no count."""

    def q(cypher: str, params: dict):
        return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    apply_schema(client, graph)
    q(
        "MERGE (o:Org {id: $id}) SET o.name = $id, o.pack = 'oss', "
        "o.connected_by = 'public_record'",
        {"id": org_id},
    )
    if commits:
        q(
            """UNWIND $rows AS r
               MERGE (a:Actor {hid: r.hid}) SET a.kind = 'human'
               MERGE (c:Action {ref: r.sha}) SET c.kind = 'commit', c.at = r.at
               MERGE (a)-[d:DID]->(c) SET d.at = r.at""",
            {"rows": commits},
        )
    tagged = [r for r in releases if r["hid"]]
    if tagged:
        q(
            """UNWIND $rows AS r
               MERGE (a:Actor {hid: r.hid}) SET a.kind = 'human'
               MERGE (rel:Action {ref: r.name}) SET rel.kind = 'release', rel.at = r.at
               MERGE (p:Path {channel: 'github-release', verified: false})
               MERGE (rel)-[:VIA]->(p)
               MERGE (a)-[d:DID]->(rel) SET d.at = r.at""",
            {"rows": tagged},
        )
    untagged = [r for r in releases if not r["hid"]]
    if untagged:
        q(
            """UNWIND $rows AS r
               MERGE (rel:Action {ref: r.name}) SET rel.kind = 'release', rel.at = r.at
               MERGE (p:Path {channel: 'github-release', verified: false})
               MERGE (rel)-[:VIA]->(p)""",
            {"rows": untagged},
        )


def connect(
    repo: str,
    *,
    api: str = GITHUB_API,
    root: Path = RAW_ROOT,
    client: FalkorClient | None = None,
    progress: Progress | None = None,
    max_commit_pages: int = MAX_COMMIT_PAGES,
    fetcher_kwargs: dict | None = None,
) -> dict:
    """Run the whole flow for one public repo. Returns a result dict; never raises for a bad repo.

    A repo that is private, missing, or fails to load returns status REFUSED, NOT FOUND or FAILED
    with the reason in it.
    """
    owner, name = parse_repo(repo)
    progress = progress or Progress()
    progress.plan(STEPS)
    gid = graph_id(owner, name)
    graph = f"org_{gid}"
    client = client or FalkorClient()
    started_wall = time.perf_counter()
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result: dict[str, Any] = {
        "repo": f"{owner}/{name}",
        "org": graph,
        "label": LABEL,
        "started_at_utc": started,
        "status": "RUNNING",
        "reason": None,
    }

    token = github_token()
    fetcher = Fetcher(
        root / f"{owner}__{name}",
        auth_header=f"Bearer {token}" if token else None,
        extra_headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        **(fetcher_kwargs or {}),
    )
    base = f"{api}/repos/{owner}/{name}"
    try:
        progress.set("read repository", "running")
        meta_entry = fetcher.get(base, "repo.json")
        if meta_entry.status == 404:
            return _finish(
                result,
                progress,
                "NOT FOUND",
                "GitHub has no public repo with that name",
                started_wall,
                fetcher,
            )
        meta = meta_entry.json()
        if meta.get("private"):
            return _finish(
                result,
                progress,
                "REFUSED",
                "the repo is private; only public repos are read",
                started_wall,
                fetcher,
            )
        progress.set("read repository", "done", meta.get("full_name"))

        progress.set("read commit history", "running")
        commits: list[dict] = []
        url, page = f"{base}/commits?per_page={PER_PAGE}", 1
        while url and page <= max_commit_pages:
            entry = fetcher.get(url, f"commits_p{page:03d}.json")
            if entry.status != 200:
                raise FetchError(f"commits page {page} returned HTTP {entry.status}")
            commits += entry.json()
            progress.set("read commit history", "running", f"{len(commits)} commits, page {page}")
            url, page = entry.next_url(), page + 1
        progress.set("read commit history", "done", f"{len(commits)} commits")

        progress.set("read releases", "running")
        rel_entry = fetcher.get(f"{base}/releases?per_page={PER_PAGE}", "releases_p001.json")
        releases = rel_entry.json() if rel_entry.status == 200 else []
        progress.set("read releases", "done", f"{len(releases)} releases")

        salt = load_salt()
        commit_rows, skipped = _commit_rows(commits, salt)
        release_rows = _release_rows(releases, salt)
        progress.set("load org graph", "running")
        load_graph(client, graph, gid, commit_rows, release_rows)
        progress.set(
            "load org graph", "done", f"{len(commit_rows)} commits, {len(release_rows)} releases"
        )

        times = [r["at"] for r in commit_rows + release_rows]
        T = max(times) if times else int(time.time())
        result["T_iso"] = utc_iso(T)
        result["counts"] = {
            "commits_read": len(commits),
            "commits_loaded": len(commit_rows),
            "commits_without_identity": skipped,
            "releases_loaded": len(release_rows),
            "actors": len({r["hid"] for r in commit_rows}),
        }

        progress.set("normal metrics", "running")
        computed = [
            M.commit_cadence_days(client, gid, T),
            M.active_keepers_as_of_T(client, gid, T),
            M.release_channel_as_of_T(client, gid, T),
        ]
        for res in computed:
            M.store(client, gid, res)
        result["metrics"] = {
            "cadence_days": _metric(computed[0]),
            "active_keepers": _metric(computed[1]),
            "usual_path": _metric(computed[2]),
        }
        progress.set("normal metrics", "done")

        tc = takeover_cost(client, gid, PRIVILEGE, T)
        progress.set("takeover cost", "done", tc.status)
        takeover = asdict(tc)
        takeover.pop("queries", None)
        takeover.pop("path", None)
        takeover["reason"] = takeover["reason"] or (NO_GRANTS if tc.status != "COMPUTED" else None)
        result["takeover_cost"] = takeover

        g = guardians(client, gid, PRIVILEGE, T)
        progress.set("guardians", "done", g.status)
        guard = asdict(g)
        guard.pop("queries", None)
        guard.pop("path", None)
        result["guardians"] = guard

        if tc.status == "COMPUTED":
            progress.set("hardening step", "done", "see below")
            result["best_hardening_step"] = _not_computed(
                "not run: this flow only reads the public record; the hardening simulator needs a "
                "measured privilege graph (core/hardening)"
            )
        else:
            progress.set("hardening step", "done", NOT_COMPUTED)
            result["best_hardening_step"] = _not_computed(
                f"takeover cost is {tc.status}, so no hardening step can be measured: {NO_GRANTS}"
            )
        return _finish(result, progress, "DONE", None, started_wall, fetcher)
    except Exception as e:  # any failure is reported in the result, with the step it stopped at
        failed = next((s.name for s in progress.steps if s.status == "running"), "read repository")
        progress.set(failed, "failed", str(e)[:200])
        return _finish(
            result,
            progress,
            "FAILED",
            f"{failed}: {type(e).__name__}: {e}"[:300],
            started_wall,
            fetcher,
        )


def _finish(result, progress, status, reason, started_wall, fetcher) -> dict:
    result["status"] = status
    result["reason"] = reason
    result["wall_clock_s"] = round(time.perf_counter() - started_wall, 3)
    result["finished_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["requests"] = {"network": fetcher.network_requests, "from_cache": fetcher.cache_hits}
    result["steps"] = progress.snapshot()
    result.setdefault("metrics", {})
    result.setdefault("takeover_cost", _not_computed(reason or "not reached"))
    result.setdefault("guardians", _not_computed(reason or "not reached"))
    result.setdefault("best_hardening_step", _not_computed(reason or "not reached"))
    return result


# ---------------------------------------------------------------- jobs (what the UI polls)

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def start_job(repo: str, **kwargs) -> str:
    """Start connect() in a thread. Returns the job id. The job's progress is readable at once."""
    parse_repo(repo)  # refuse bad text before a thread starts
    job_id = uuid.uuid4().hex
    progress = Progress()
    job = {
        "id": job_id,
        "repo": repo.strip(),
        "state": "running",
        "progress": progress,
        "result": None,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job

    def run() -> None:
        try:
            job["result"] = connect(repo, progress=progress, **kwargs)
            job["state"] = "done"
        except Exception as e:
            job["result"] = {"status": "FAILED", "reason": f"{type(e).__name__}: {e}"[:300]}
            job["state"] = "failed"

    threading.Thread(target=run, daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        return None
    return {
        "id": job["id"],
        "repo": job["repo"],
        "state": job["state"],
        "steps": job["progress"].snapshot(),
        "result": job["result"],
    }
