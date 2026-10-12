"""Who a note goes to (spec 12.2, Routing and hand-off). Deterministic. No model, no graph reads.

Rules, in order:
1. The note goes to the owner.
2. With two or more keepers it goes to all of them in one shared private thread.
3. A single-keeper note goes to the backup the owner named, but only if the owner is marked
   away or the note went unacknowledged for 48 hours.
4. Never to a flagged account. Never to anyone the owner did not name or who is not a keeper:
   the recipients are always a subset of {owner, keepers, backup}.
Nothing is sent. The result says where the note would go and why.
"""

from dataclasses import dataclass, field

UNACKED_HOURS = 48  # spec 12.2: "a previous note went unacknowledged for 48 h"
HOUR_S = 3600


@dataclass(frozen=True)
class Route:
    recipients: tuple[str, ...]
    thread: str  # 'private' or 'shared'
    backup_used: bool
    reason: str
    waiting: bool = False  # the note stays with an owner who is away: no usable backup
    flagged_removed: tuple[str, ...] = field(default_factory=tuple)


def route_note(
    *,
    owner: str,
    keepers: list[str],
    backup: str | None,
    away: bool,
    created_at: int,
    ack_at: int | None,
    now: int,
    flagged: list[str] | tuple[str, ...] = (),
) -> Route:
    bad = set(flagged) - {owner}  # the owner is the person in charge, never "flagged"
    removed = tuple(sorted(({owner, backup, *keepers} - {None}) & bad))  # type: ignore[arg-type]
    clean_keepers = sorted({k for k in keepers if k not in bad})
    unacked = ack_at is None and (now - created_at) >= UNACKED_HOURS * HOUR_S
    needs_backup = away or unacked

    if len(clean_keepers) >= 2:
        recipients = (
            tuple(dict.fromkeys([owner, *clean_keepers]))
            if owner in clean_keepers
            else tuple(clean_keepers)
        )
        route = Route(
            recipients,
            "shared",
            False,
            f"{len(recipients)} keepers: one shared private thread, so no one holds it alone",
            flagged_removed=removed,
        )
    elif not needs_backup:
        route = Route((owner,), "private", False, "the owner is available", flagged_removed=removed)
    else:
        trigger = (
            "the owner is marked away" if away else f"no acknowledgement for {UNACKED_HOURS} h"
        )
        if backup is None:
            route = Route(
                (owner,),
                "private",
                False,
                f"{trigger}, but no backup is named: the note waits for the owner",
                waiting=True,
                flagged_removed=removed,
            )
        elif backup in bad:
            route = Route(
                (owner,),
                "private",
                False,
                f"{trigger}, but the named backup is flagged: the note waits for the owner",
                waiting=True,
                flagged_removed=removed,
            )
        else:
            route = Route(
                (backup,),
                "private",
                True,
                f"{trigger}: routed to the backup the owner named",
                flagged_removed=removed,
            )
    allowed = {owner, *keepers} | ({backup} if backup else set())
    if not set(route.recipients) <= allowed or set(route.recipients) & bad:
        raise AssertionError("routing widened the audience or reached a flagged account")
    return route
