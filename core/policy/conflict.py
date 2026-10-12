"""Conflict policy for two contradictory claims (docs/HEARTHGUARD.md §7.2, FROZEN).

Pure function. No graph access, no LLM. Claims are kept as written: the result links them and
never deletes either. The rules are applied in the spec's order:

  1. Authority:   owner decision > system record > established actor > low-history actor > hearsay.
  2. Specificity: an explicit exception narrows a general statement (both stand).
  3. Recency:     the newer claim wins between equals.
  4. UNRESOLVED:  equal authority and still conflicting. No winner is picked.

Reading choices (PROPOSED, docs/decisions/0003-conflict-policy-reading.md):
  - The caller supplies each claim's authority class (`source`) and, for a specificity relation,
    `exception_to` (the id of the general claim it narrows). This module does not classify actors.
  - Taken in the spec's order, recency separates every equal-authority pair with two different
    times. So UNRESOLVED arises when the times are equal or one is missing. A missing time is
    never defaulted.
"""

from dataclasses import dataclass

# Lowest to highest. The position is the rank.
AUTHORITY_ORDER: tuple[str, ...] = (
    "hearsay",
    "low_history_actor",
    "established_actor",
    "system_record",
    "owner_decision",
)
RANK = {name: i for i, name in enumerate(AUTHORITY_ORDER)}

RESOLVED = "RESOLVED"
NARROWED = "NARROWED"
UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class Claim:
    id: str
    source: str  # one of AUTHORITY_ORDER
    at: int | None = None  # Unix seconds, or None if unknown
    exception_to: str | None = None  # id of the general claim this one is an explicit exception to


@dataclass(frozen=True)
class Resolution:
    status: str  # RESOLVED, NARROWED or UNRESOLVED
    claim_ids: tuple[str, str]  # both claims, in the order given. Both are always kept.
    winner: str | None  # None when NARROWED or UNRESOLVED
    basis: str
    links: tuple[tuple[str, str, str], ...]  # (from id, relation, to id), §6.1 claim relations


def _validate(claims) -> tuple[Claim, Claim]:
    if len(claims) != 2:
        raise ValueError(f"resolve() takes exactly two contradictory claims, got {len(claims)}")
    a, b = claims
    if a.id == b.id:
        raise ValueError("the two claims must have different ids")
    for c in (a, b):
        if c.source not in RANK:
            raise ValueError(
                f"unknown authority class {c.source!r}; expected one of {AUTHORITY_ORDER}"
            )
        if c.at is not None and (isinstance(c.at, bool) or not isinstance(c.at, int)):
            raise ValueError("claim time must be an integer or None")
    if a.exception_to == b.id and b.exception_to == a.id:
        raise ValueError("two claims cannot each be an exception to the other")
    return a, b


def resolve(claims) -> Resolution:
    a, b = _validate(claims)
    ids = (a.id, b.id)
    contradicts = (a.id, "CONTRADICTS", b.id)

    # 1. Authority.
    if RANK[a.source] != RANK[b.source]:
        winner = a if RANK[a.source] > RANK[b.source] else b
        return Resolution(RESOLVED, ids, winner.id, "authority", (contradicts,))

    # 2. Specificity: an explicit exception narrows the general statement. Both stand.
    for exception, general in ((a, b), (b, a)):
        if exception.exception_to == general.id:
            return Resolution(
                NARROWED,
                ids,
                None,
                "specificity",
                (contradicts, (exception.id, "QUALIFIES", general.id)),
            )

    # 3. Recency, between equals. Needs two known and different times.
    if a.at is not None and b.at is not None and a.at != b.at:
        newer, older = (a, b) if a.at > b.at else (b, a)
        return Resolution(
            RESOLVED, ids, newer.id, "recency", (contradicts, (newer.id, "SUPERSEDES", older.id))
        )

    # 4. Equal authority and still conflicting. Never pick a winner.
    return Resolution(
        UNRESOLVED, ids, None, "equal authority, no way to order them", (contradicts,)
    )
