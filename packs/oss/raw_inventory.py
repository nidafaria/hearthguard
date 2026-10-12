"""Write eval/results/xz_raw_inventory.json: what is cached, with counts and dates only.

For each source: how many responses and items are cached, the earliest and latest date among the
items, and when they were fetched. The file holds no name, no email, no subject and no URL (the
mailing list's address contains an @). Nothing here is a finding; it describes the cache.
"""

import json
from pathlib import Path

from packs.oss import github_cache, mail_cache
from packs.oss.raw_cache import Fetcher, utc_now_iso

OUT = Path(__file__).resolve().parents[2] / "eval" / "results" / "xz_raw_inventory.json"

# The date field to read from each kind of GitHub item.
DATE_FIELDS = {
    "pull_requests": lambda x: x.get("created_at"),
    "reviews": lambda x: x.get("submitted_at"),
    "review_comments": lambda x: x.get("created_at"),
    "issue_comments": lambda x: x.get("created_at"),
    "file_history": lambda x: (x.get("commit", {}).get("committer") or {}).get("date"),
}
GROUP_OF_PREFIX = (
    ("pulls_state-all_", "pull_requests"),
    ("commits_path-", "file_history"),
)


def _group_of(body_name: str) -> str | None:
    for prefix, group in GROUP_OF_PREFIX:
        if body_name.startswith(prefix):
            return group
    for kind in ("reviews", "review_comments", "issue_comments"):
        if body_name.startswith("pr-") and f"_{kind}_p" in body_name:
            return kind
    return None


def _span(dates: list[str]) -> tuple[str | None, str | None]:
    return (min(dates), max(dates)) if dates else (None, None)


def github_inventory(root: Path = github_cache.RAW_ROOT) -> dict:
    groups: dict[str, dict] = {
        g: {"responses": 0, "items": 0, "dates": [], "fetched": [], "authenticated": 0}
        for g in DATE_FIELDS
    }
    for meta_path in sorted(root.glob("*.json.meta.json")):
        name = meta_path.name.removesuffix(".meta.json")
        group = _group_of(name)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # A sidecar whose body is gone is not a cached response (the crawl would fetch it again).
        if group is None or meta["status"] != 200 or not (root / name).is_file():
            continue
        g = groups[group]
        g["responses"] += 1
        g["fetched"].append(meta["fetched_at_utc"])
        g["authenticated"] += bool(meta.get("authenticated"))
        for item in json.loads((root / name).read_text(encoding="utf-8")):
            g["items"] += 1
            d = DATE_FIELDS[group](item)
            if d:
                g["dates"].append(d)

    sources = {}
    for group, g in groups.items():
        earliest, latest = _span(g["dates"])
        first, last = _span(g["fetched"])
        sources[group] = {
            "responses": g["responses"],
            "items": g["items"],
            "earliest": earliest,
            "latest": latest,
            "fetched_first_utc": first,
            "fetched_last_utc": last,
            "responses_with_token": g["authenticated"],
        }
    fetcher = Fetcher(root, min_interval_s=0)  # only used to read the cache, never to fetch
    todo = github_cache.missing(fetcher)
    fetcher.close()
    return {
        "repo": f"{github_cache.OWNER}/{github_cache.REPO}",
        "complete": bool(sources["pull_requests"]["responses"]) and not todo,
        "requests_still_missing_at_least": len(todo),
        "token_configured_now": github_cache.github_token() is not None,
        "sources": sources,
    }


def mail_inventory(root: Path = mail_cache.RAW_ROOT) -> dict:
    rows = mail_cache.build_index(root)
    found = [r for r in rows if r["status"] == 200]
    scoped = [r for r in found if r["in_scope"]]
    dates = [r["date_utc"] for r in scoped if r["date_utc"]]
    earliest, latest = _span(dates)
    first, last = _span([r["fetched_at_utc"] for r in rows])
    newest = max((r["msg"] for r in found), default=0)
    missing_inside = [r for r in rows if r["status"] != 200 and r["msg"] < newest]
    return {
        "list": "xz-devel",
        "window": ["2021-01-01", "2024-12-31"],
        "also_explicitly": ["msg00512", "msg00571"],
        "messages_in_scope": len(scoped),
        "earliest": earliest,
        "latest": latest,
        "messages_cached_total": len(found),
        "newest_message_number": newest,
        "message_numbers_not_found_below_newest": len(missing_inside),
        "fetched_first_utc": first,
        "fetched_last_utc": last,
        "author_identifiers": "hashed; the archive shows a display name only, so names are hashed",
    }


def build_inventory() -> dict:
    return {
        "generated_at_utc": utc_now_iso(),
        "note": (
            "Describes the raw cache only. Counts and dates, no names, emails, subjects or URLs. "
            "Nothing has been added to the graph. Not a finding."
        ),
        "github": github_inventory(),
        "mailing_list": mail_inventory(),
    }


def write_inventory(path: Path = OUT) -> dict:
    inv = build_inventory()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")
    return inv
