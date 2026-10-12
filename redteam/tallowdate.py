"""Seeded synthetic history for the fictional `tallowdate` project (spec §3.5 Part 2, §18).

Every entity is fictional and carries synthetic: true. Planted entities also carry planted: true
and a campaign_id. Detectors never read these flags; only the scorer does.

Run: uv run python -m redteam.tallowdate  (writes data/synthetic/tallowdate.json)
The same seed gives the same bytes on every run.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

SEED = 20260412
CASE = "tallowdate"
CAMPAIGN_ID = "tallowdate-campaign-1"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "tallowdate.json"

# The only people in this case. Accounts are labelled by role, not by name.
MIRA = "Mira"  # sole maintainer, nine years, maintains at night
TOMAS = "Tomás"  # has reviewed her pull requests for three years, never asked for rights
ROWAN = "Rowan"  # planted persona
PLANTED_ACCOUNTS = ("acct-a", "acct-b", "acct-c")  # three new accounts, same creation week

# Background: Tomás's reviews before the story starts, generated (not a claim about any person).
REVIEW_COUNT = 140
REVIEW_WINDOW = (dt.date(2023, 4, 1), dt.date(2025, 12, 31))


def _event(
    date: dt.date,
    actor: str,
    kind: str,
    summary: str,
    *,
    move: str | None = None,
    where: str | None = None,
    planted: bool = False,
) -> dict:
    return {
        "date": date.isoformat(),
        "actor": actor,
        "kind": kind,
        "summary": summary,
        "move": move,
        "where": where,
        "planted": planted,
        "campaign_id": CAMPAIGN_ID if planted else None,
        "synthetic": True,
    }


def _background_reviews(rng: random.Random) -> list[dict]:
    start, end = REVIEW_WINDOW
    span = (end - start).days
    offsets = sorted(rng.sample(range(span + 1), REVIEW_COUNT))
    return [
        _event(
            start + dt.timedelta(days=off),
            TOMAS,
            "pr_review",
            "Reviewed a pull request in the project.",
            where="pull requests",
        )
        for off in offsets
    ]


def _story_events() -> list[dict]:
    d = dt.date
    rowan = dict(planted=True)
    return [
        _event(
            d(2026, 1, 9),
            ROWAN,
            "pr_merged",
            "Sent a small, useful patch. Merged.",
            where="pull requests",
            **rowan,
        ),
        _event(
            d(2026, 1, 17),
            ROWAN,
            "pr_merged",
            "Sent a second small patch. Merged.",
            where="pull requests",
            **rowan,
        ),
        _event(
            d(2026, 1, 28), MIRA, "comment", "Thanked Rowan for the patches.", where="pull requests"
        ),
        _event(
            d(2026, 1, 30),
            ROWAN,
            "pr_merged",
            "Sent a third patch. Merged.",
            where="pull requests",
            **rowan,
        ),
        _event(d(2026, 2, 10), "acct-a", "account_created", "Account created.", planted=True),
        _event(d(2026, 2, 11), "acct-b", "account_created", "Account created.", planted=True),
        _event(d(2026, 2, 12), "acct-c", "account_created", "Account created.", planted=True),
        _event(
            d(2026, 2, 14),
            "acct-a",
            "issue_opened",
            'Opened an issue: "Is this abandoned?"',
            move="Pressure",
            where="issues",
            planted=True,
        ),
        _event(
            d(2026, 2, 20),
            "acct-c",
            "comment",
            "Vouched for Rowan in an issue.",
            move="Vouch",
            where="issues",
            planted=True,
        ),
        _event(
            d(2026, 3, 3),
            "acct-b",
            "issue_opened",
            'Opened an issue: "Rowan should be co-maintainer."',
            move="Pressure",
            where="issues",
            planted=True,
        ),
        _event(
            d(2026, 3, 20),
            MIRA,
            "post",
            '"Sorry all, new job, I\'m swamped."',
            move="Capacity statement",
            where="issues",
        ),
        _event(
            d(2026, 4, 10),
            TOMAS,
            "role_accepted",
            "Accepted the co-keeper role. Releases need two keepers and provenance.",
            where="maintainers",
        ),
        _event(
            d(2026, 5, 6),
            ROWAN,
            "rights_requested",
            "Asked for release rights.",
            move="Rush",
            where="maintainers",
            planted=True,
        ),
        _event(
            d(2026, 6, 8), MIRA, "absence", "First week off in four years.", where="maintainers"
        ),
        _event(
            d(2026, 6, 10),
            TOMAS,
            "release_signed",
            "Shipped 1.4.2, signed by two keepers.",
            where="releases",
        ),
    ]


def build_events() -> list[dict]:
    """All events in order: background reviews, then the story. Same seed, same list."""
    rng = random.Random(SEED)
    events = _background_reviews(rng) + _story_events()
    events.sort(key=lambda e: e["date"])  # stable sort keeps same-day order as built
    for seq, e in enumerate(events, start=1):
        e["id"] = f"{CASE}-{seq:04d}"
        e["seq"] = seq
    return events


def build_case() -> dict:
    return {
        "case": CASE,
        "label": "SYNTHETIC: fictional project, fictional people",
        "synthetic": True,
        "seed": SEED,
        "people": [
            {
                "name": MIRA,
                "role": "sole maintainer",
                "synthetic": True,
                "planted": False,
                "campaign_id": None,
            },
            {
                "name": TOMAS,
                "role": "reviewer",
                "synthetic": True,
                "planted": False,
                "campaign_id": None,
            },
            {
                "name": ROWAN,
                "role": "planted persona",
                "synthetic": True,
                "planted": True,
                "campaign_id": CAMPAIGN_ID,
            },
        ],
        "events": build_events(),
    }


def write_case(path: Path = OUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(build_case(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main() -> None:
    path = write_case()
    count = len(json.loads(path.read_text(encoding="utf-8"))["events"])
    print(f"wrote {path} with {count} events (synthetic)")


if __name__ == "__main__":
    main()
