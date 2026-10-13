"""The deterministic filler (docs/decisions/0007-learned-exception-filler.md). Pure. No LLM.

The spec has the Liaison propose a template with an LLM (8.3 step 2). This block does not use one:
the proposal is a fixed table from dismissal words to building blocks, so the same reason always
gives the same template and the chaos runs need no model calls. The owner's reason is data; it
only selects a row of the table and is never copied into the template.

Up to MAX_ATTEMPTS attempts. Attempt 1 matches whole words, attempt 2 matches word stems. If no
attempt yields a template that passes templates.validate(), the filler returns None and the
caller sends the case to Human review (8.3 step 2: "up to 3 attempts, then a human writes it").
"""

import re
from dataclasses import dataclass, field

from core.learning import templates as tp

MAX_ATTEMPTS = 3

# (words, move, clauses). Each row is one fixed proposal. Pressure is the move a newcomer or
# bot noise drives; Vouch is an endorsement pattern; Rush is a release-timing pattern.
TABLE = (
    (
        ("bot", "bots", "dependabot", "renovate", "ci"),
        "PRESSURE",
        ("actor.kind == 'bot'", "actor.hid IN org.declared_bots"),
        "bots_are_not_newcomers",
    ),
    (
        ("handover", "handoff", "announced"),
        "VOUCH",
        ("actor.hid IN org.declared_handover",),
        "announced_handover_is_not_vouching",
    ),
    (
        ("contact", "vendor", "phone", "email"),
        "RUSH",
        ("actor.hid IN org.declared_contacts",),
        "vendor_contact_change_is_not_rush",
    ),
)


@dataclass
class Proposal:
    template: tp.ExceptionTemplate | None
    attempts: list[dict] = field(default_factory=list)


def _words(reason: str) -> list[str]:
    return re.findall(r"[a-z]+", reason.lower())


def _row_for(reason: str, attempt: int):
    words = _words(reason)
    for row in TABLE:
        keys = row[0]
        if attempt == 1:
            hit = any(w in keys for w in words)
        else:  # attempt 2: a word starts with a key (stems: "handed" misses, "handover" hits)
            hit = any(w.startswith(k) for w in words for k in keys)
        if hit:
            return row
    return None


def propose(reason: str) -> Proposal:
    """A template for this dismissal reason, or None after MAX_ATTEMPTS failed attempts."""
    attempts: list[dict] = []
    for n in range(1, MAX_ATTEMPTS + 1):
        row = _row_for(reason, n)
        if row is None:
            attempts.append({"attempt": n, "ok": False, "error": "no building block matches"})
            continue
        _, move, clauses, name = row
        template, error = tp.validate(
            {
                "exception": name,
                "applies_to": f"move.{move}",
                "when": " AND ".join(clauses),
                "effect": tp.EFFECT,
            }
        )
        attempts.append({"attempt": n, "ok": template is not None, "error": error})
        if template is not None:
            return Proposal(template, attempts)
    return Proposal(None, attempts)
