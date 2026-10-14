"""Cache the public record of the event-stream (2018) and axios (2026) incidents (spec §3.1, R6).

  uv run python -m eval.incidents_fetch

Every response is saved once under data/raw/incidents/ with a `.meta.json` sidecar (URL, fetch
time, status) by packs/oss/raw_cache.Fetcher, and is never fetched again. Writes
eval/results/incidents_fetch.json: each source, its URL, its fetch time and size. No identifier is
read here; hashing happens when the files are parsed (packs/oss/npm.py, packs/oss/tracker.py).

Sources, and why each is here:
  npm registry packument   release time, publisher (`_npmUser`) and maintainers of every version
  OSV record               the advisory that names the malicious versions (primary advisory)
  GitHub issues            the public reports (event-stream #115, #116; axios #10604)
  StepSecurity write-up    SECONDARY. Quotes the registry metadata of the removed axios versions;
                           it is the only cached place that says how 1.14.1 was published. It is
                           labelled secondary wherever it is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from packs.oss.github_cache import github_token
from packs.oss.raw_cache import Fetcher

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "incidents"
OUT = ROOT / "eval" / "results" / "incidents_fetch.json"

NPM = "https://registry.npmjs.org"
OSV = "https://api.osv.dev/v1/vulns"
GH = "https://api.github.com/repos"

SOURCES: list[dict] = [
    {
        "case": "event_stream",
        "name": "event_stream/npm_event-stream.json",
        "url": f"{NPM}/event-stream",
        "kind": "npm_packument",
    },
    {
        "case": "event_stream",
        "name": "event_stream/osv_GHSA-mh6f-8j2x-4483.json",
        "url": f"{OSV}/GHSA-mh6f-8j2x-4483",
        "kind": "advisory",
    },
    {
        "case": "event_stream",
        "name": "event_stream/issue_115.json",
        "url": f"{GH}/dominictarr/event-stream/issues/115",
        "kind": "github_issue",
    },
    {
        "case": "event_stream",
        "name": "event_stream/issue_115_comments.json",
        "url": f"{GH}/dominictarr/event-stream/issues/115/comments?per_page=100",
        "kind": "github_comments",
    },
    {
        "case": "event_stream",
        "name": "event_stream/issue_116.json",
        "url": f"{GH}/dominictarr/event-stream/issues/116",
        "kind": "github_issue",
    },
    {
        "case": "axios",
        "name": "axios/npm_axios.json",
        "url": f"{NPM}/axios",
        "kind": "npm_packument",
    },
    {
        "case": "axios",
        "name": "axios/osv_MAL-2026-2307.json",
        "url": f"{OSV}/MAL-2026-2307",
        "kind": "advisory",
    },
    {
        "case": "axios",
        "name": "axios/issue_10604.json",
        "url": f"{GH}/axios/axios/issues/10604",
        "kind": "github_issue",
    },
    {
        "case": "axios",
        "name": "axios/stepsecurity_writeup.html",
        "url": "https://www.stepsecurity.io/blog/axios-compromised-on-npm-malicious-versions-"
        "drop-remote-access-trojan",
        "kind": "secondary_writeup",
    },
]


def fetch_all(root: Path = RAW, log=print) -> dict:
    token = github_token()
    fetcher = Fetcher(root, auth_header=f"Bearer {token}" if token else None, log=log)
    rows = []
    try:
        for s in SOURCES:
            e = fetcher.get(s["url"], s["name"])
            size = e.body_path.stat().st_size if e.body_path else 0
            rows.append(
                {
                    **s,
                    "status": e.status,
                    "bytes": size,
                    "fetched_at": e.meta.get("fetched_at_utc"),
                    "from_cache": e.from_cache,
                }
            )
    finally:
        fetcher.close()
    return {
        "scope": "public records only (npm registry, OSV, GitHub issues, one security write-up "
        "labelled secondary); cached under data/raw/incidents/ (git-ignored)",
        "sources": rows,
        "all_ok": all(r["status"] == 200 for r in rows),
    }


def main() -> int:
    doc = fetch_all()
    # from_cache differs between a first and a later run; it is not part of the record.
    for r in doc["sources"]:
        r.pop("from_cache")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for r in doc["sources"]:
        print(f"{r['status']} {r['bytes']:>9}  {r['name']}")
    return 0 if doc["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
