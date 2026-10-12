"""Task 1: fetch the public records for the xz ecosystem places and cache them.

Each response is saved under data/raw/ecosystem/ as `<name>` plus `<name>.meta.json` (URL, fetch
time, HTTP status, byte counts). Before anything is written, every email address in the body is
replaced by a token `[email-hash:<hmac>]`, so no email reaches disk but the same address still
hashes to the same value everywhere. A source that cannot be fetched is recorded with its status
and no body; nothing is invented.

CORE sources are the four named in the task. SUPPLEMENTARY sources give exact timestamps, the
reviewers' roles, and the earlier footprint of the identity behind the Debian request.
"""

import json
import re
import time
from pathlib import Path

import httpx

from core.graph.hashing import identifier_hash, load_salt
from packs.oss.raw_cache import USER_AGENT, utc_now_iso

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "ecosystem"
SOURCES_OUT = ROOT / "eval" / "results" / "ecosystem_sources.json"

# Any address, including a truncated one like `name@host ...` that an archive page may show.
EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+\-]+(?:@|&#64;|&commat;)[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*")
TOKEN_RE = re.compile(r"\[email-hash:([0-9a-f]{64})\]")

OSSF = "https://github.com/google/oss-fuzz/commit/{}.patch"
GH = "https://api.github.com/repos/{}"
LKML = "https://lkml.org/lkml/2024/3/{}"
LP = "https://api.launchpad.net/1.0/bugs/2059417"
XZ_COMMITS = [
    "23b5c36fb71904bfbe16bb20f976da38dadf6c3b",
    "b72d21202402a603db6d512fb9271cfa83249639",
    "233885a437f8b55a5c8442984ebc0aaa579e92de",
    "93e6fb08b22c7c13be2dd1e7274fe78413436254",
    "f1cd9d7194f005cd66ec03c6635ceae75f90ef17",
]

# (id, place, label, cache file, url, core)
SOURCES = [
    (
        "oss_fuzz_6403e933",
        "oss-fuzz",
        "oss-fuzz commit 6403e933",
        "oss_fuzz_6403e933.patch",
        OSSF.format("6403e933"),
        True,
    ),
    (
        "oss_fuzz_d2e42b2e",
        "oss-fuzz",
        "oss-fuzz commit d2e42b2e",
        "oss_fuzz_d2e42b2e.patch",
        OSSF.format("d2e42b2e"),
        True,
    ),
    (
        "lkml_2024_3_20_1008",
        "lkml",
        "LKML message 2024/3/20/1008",
        "lkml_2024_3_20_1008.html",
        LKML.format("20/1008"),
        True,
    ),
    (
        "debian_bug_1067708",
        "debian-bts",
        "Debian bug 1067708",
        "debian_bug_1067708.html",
        "https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1067708",
        True,
    ),
    (
        "launchpad_bug_2059417",
        "launchpad",
        "Ubuntu Launchpad bug 2059417",
        "launchpad_bug_2059417.html",
        "https://bugs.launchpad.net/ubuntu/+source/xz-utils/+bug/2059417",
        True,
    ),
]


def _supp(sid: str, place: str, label: str, name: str, url: str) -> None:
    SOURCES.append((sid, place, label, name, url, False))


# exact timestamps, handles and reviewer roles for oss-fuzz
for _sha in ("6403e933", "d2e42b2e"):
    _supp(
        f"gh_ossfuzz_commit_{_sha}",
        "oss-fuzz",
        f"GitHub API: oss-fuzz commit {_sha}",
        f"gh_ossfuzz_commit_{_sha}.json",
        GH.format(f"google/oss-fuzz/commits/{_sha}"),
    )
for _pr in (9960, 10667):
    for _suffix, _path in (
        ("", f"google/oss-fuzz/pulls/{_pr}"),
        ("_reviews", f"google/oss-fuzz/pulls/{_pr}/reviews"),
        ("_comments", f"google/oss-fuzz/issues/{_pr}/comments?per_page=100"),
    ):
        _supp(
            f"gh_ossfuzz_pr_{_pr}{_suffix}",
            "oss-fuzz",
            f"GitHub API: oss-fuzz PR {_pr}{_suffix.replace('_', ' ')}",
            f"gh_ossfuzz_pr_{_pr}{_suffix}.json",
            GH.format(_path),
        )
# LKML thread replies (reviewer roles and dates)
for _n in (1289, 1350, 1475):
    _supp(
        f"lkml_2024_3_29_{_n}",
        "lkml",
        f"LKML reply 2024/3/29/{_n}",
        f"lkml_2024_3_29_{_n}.html",
        LKML.format(f"29/{_n}"),
    )
# Launchpad exact dates
for _what, _suffix in (("bug", ""), ("messages", "/messages"), ("activity", "/activity")):
    _supp(
        f"lp_api_{_what}",
        "launchpad",
        f"Launchpad API: bug 2059417 {_what}",
        f"lp_api_{_what}.json",
        LP + _suffix,
    )
# the earlier footprint, in xz-git, of the identity behind the Debian request
for _sha in XZ_COMMITS:
    _supp(
        f"gh_xz_commit_{_sha[:8]}",
        "xz-git",
        f"GitHub API: xz commit {_sha[:8]}",
        f"gh_xz_commit_{_sha[:8]}.json",
        GH.format(f"tukaani-project/xz/commits/{_sha}"),
    )


def _redact_json(value, salt: bytes):
    """Redact inside decoded JSON strings, so a `\n` escape can never be eaten by the match."""
    if isinstance(value, str):
        out, n = redact(value.encode("utf-8"), salt)
        return out.decode("utf-8"), n
    if isinstance(value, list):
        pairs = [_redact_json(v, salt) for v in value]
        return [p[0] for p in pairs], sum(p[1] for p in pairs)
    if isinstance(value, dict):
        pairs = {k: _redact_json(v, salt) for k, v in value.items()}
        return {k: p[0] for k, p in pairs.items()}, sum(p[1] for p in pairs.values())
    return value, 0


def redact_body(body: bytes, name: str, salt: bytes) -> tuple[bytes, int]:
    """Redact a whole response. JSON is redacted value by value, anything else as text."""
    if name.endswith(".json"):
        try:
            obj, n = _redact_json(json.loads(body), salt)
            return (json.dumps(obj, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), n
        except ValueError:
            pass
    return redact(body, salt)


def redact(body: bytes, salt: bytes) -> tuple[bytes, int]:
    """Replace each email with a hash token. Returns the new body and how many were replaced."""
    count = 0

    def sub(m: re.Match) -> bytes:
        nonlocal count
        count += 1
        addr = m.group(0).decode("utf-8", "replace").replace("&#64;", "@").replace("&commat;", "@")
        h = identifier_hash("email:" + addr.strip().lower(), salt=salt)
        return f"[email-hash:{h}]".encode()

    return EMAIL_RE.sub(sub, body), count


def fetch_one(client: httpx.Client, url: str, name: str, salt: bytes) -> dict:
    """Fetch once; reuse the cache when the sidecar exists. Returns the sidecar dict."""
    body_path = RAW_DIR / name
    meta_path = RAW_DIR / f"{name}.meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["status"] != 200 or body_path.is_file():
            return meta
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    status, raw, err = None, b"", None
    for attempt in range(1, 4):
        try:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            status, raw = resp.status_code, resp.content
            if status in (200, 404):
                break
        except httpx.TransportError as e:
            err = type(e).__name__
        time.sleep(2**attempt)
    redacted, n = redact_body(raw, name, salt)
    meta = {
        "url": url,
        "fetched_at_utc": utc_now_iso(),
        "status": status,
        "bytes": len(raw),
        "stored_bytes": len(redacted) if status == 200 else 0,
        "emails_hashed_before_storing": n,
        "error": err if status is None else None,
    }
    if status == 200:
        body_path.write_bytes(redacted)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def row(sid, place, label, name, url, meta) -> dict:
    ok = meta["status"] == 200
    return {
        "id": sid,
        "place": place,
        "label": label,
        "url": url,
        "cache_file": f"data/raw/ecosystem/{name}",
        "status": meta["status"],
        "result": "FETCHED" if ok else "NOT COMPUTED",
        "reason": None if ok else f"HTTP status {meta['status']}",
        "fetched_at_utc": meta["fetched_at_utc"],
        "bytes": meta["bytes"],
        "emails_hashed_before_storing": meta["emails_hashed_before_storing"],
    }


def run() -> dict:
    salt = load_salt()
    core, extra = [], []
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for sid, place, label, name, url, is_core in SOURCES:
            meta = fetch_one(client, url, name, salt)
            (core if is_core else extra).append(row(sid, place, label, name, url, meta))
            time.sleep(1.0)
    out = {
        "sources": core,
        "supplementary_sources": extra,
        "note": "The task's four sources are in `sources`. `supplementary_sources` are extra "
        "public records fetched for exact timestamps, reviewer roles, and the xz-git footprint.",
    }
    SOURCES_OUT.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    res = run()
    for r in res["sources"] + res["supplementary_sources"]:
        print(r["id"], r["status"], r["bytes"])
