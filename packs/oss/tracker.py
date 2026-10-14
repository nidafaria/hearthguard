"""Public bug-tracker parser (spec §4.2 source parsers): a GitHub issue and its comments.

Input is the JSON the GitHub REST API returns for `repos/<o>/<r>/issues/<n>` and its
`.../comments` list. Output is plain dicts. Logins are hashed on the way in as
`identifier_hash("github:<login>")` and never stored; the caller may name already-public,
adjudicated handles in `public_personas`. Issue and comment text is NOT returned: only who, when,
where and the public URL, which is all the graph needs (the Reader is the only code that reads
text, and it is not run here).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from core.graph.hashing import identifier_hash


def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def github_hid(login: str) -> str:
    return identifier_hash(f"github:{login.strip().lower()}")


def parse_thread(
    issue: dict,
    comments: list[dict],
    repo: str,
    hash_fn: Callable[[str], str] = github_hid,
    public_personas: frozenset[str] = frozenset(),
) -> dict:
    """One issue and its comments as events, oldest first. `repo` is `owner/name`."""
    personas: dict[str, str] = {}

    def hid_of(login: str | None) -> str | None:
        if not login:
            return None
        h = hash_fn(login)
        if login.lower() in public_personas:
            personas[h] = login
        return h

    events = [
        {
            "ref": f"{repo}#{issue['number']}",
            "kind": "issue",
            "at": epoch(issue["created_at"]),
            "actor_hid": hid_of((issue.get("user") or {}).get("login")),
            "place": f"github:{repo}",
            "url": issue.get("html_url"),
        }
    ]
    for c in comments:
        events.append(
            {
                "ref": f"{repo}#{issue['number']}/comment/{c['id']}",
                "kind": "issue",
                "at": epoch(c["created_at"]),
                "actor_hid": hid_of((c.get("user") or {}).get("login")),
                "place": f"github:{repo}",
                "url": c.get("html_url"),
            }
        )
    events.sort(key=lambda e: (e["at"], e["ref"]))
    return {
        "repo": repo,
        "number": issue["number"],
        "state": issue.get("state"),
        "events": events,
        "public_personas": personas,
    }
