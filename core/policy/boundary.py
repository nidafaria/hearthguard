"""Action boundary (docs/HEARTHGUARD.md §4.4): it asks, it never orders.

One check, `check()`, that every send path must pass before anything leaves the system. Pure
code: no graph, no LLM, no network.

  Level 0  analyse, draft, explain, simulate hardening on a copy      automatic
  Level 1  a PRIVATE note to the person in charge, phrased as a        automatic, after the
           question; answers to their follow-up questions              policy and Skeptic clear it
  Level 2  suggest a concrete safety step with its measured effect     the person in charge
                                                                       chooses whether to act
  Never    post publicly, comment on issues or PRs, revoke access, block a release or payment,
           contact the flagged account, label anyone an attacker, individual risk scores,
           publish per-project census results

Deny by default: an action that is not listed is refused, and so is a recipient who is not a
private recipient. Nothing in this repository sends a message yet. `ALLOWED_NETWORK_WRITE_MODULES`
names the only files in which an outbound write call may ever appear; tests/unit/test_boundary.py
scans the source tree and fails on any other.
"""

from enum import IntEnum


class Level(IntEnum):
    ANALYSE = 0  # analyse, draft, explain, simulate on a copy
    PRIVATE_NOTE = 1  # a private question to the person in charge
    SUGGEST_STEP = 2  # a concrete safety step; the person in charge decides


# Allowed actions and the level each one needs.
ACTIONS: dict[str, Level] = {
    "analyse": Level.ANALYSE,
    "draft": Level.ANALYSE,
    "explain": Level.ANALYSE,
    "simulate_hardening": Level.ANALYSE,
    "send_private_note": Level.PRIVATE_NOTE,
    "answer_followup": Level.PRIVATE_NOTE,
    "suggest_safety_step": Level.SUGGEST_STEP,
}

# §4.4 "Never". Each item has a name a send path can be asked about.
NEVER: dict[str, str] = {
    "post_publicly": "post publicly",
    "comment_on_issue_or_pr": "comment on issues or PRs",
    "revoke_access": "revoke access",
    "block_release_or_payment": "block a release or payment",
    "contact_flagged_account": "contact the flagged account",
    "label_attacker": "label anyone an attacker",
    "individual_risk_score": "produce individual risk scores",
    "publish_census_per_project": "publish per-project census results",
}

# Only the owner, or a backup the owner named at connect time (§12.2), may receive a note.
PRIVATE_RECIPIENTS = frozenset({"owner", "backup"})

# The only files where an outbound write call (a POST, a message send, mail) may appear. None
# exists yet, because no sender is built. core/llm/client.py POSTs to the model endpoint, which is
# a request for text, not a message to a person: it is listed separately so that is explicit.
ALLOWED_NETWORK_WRITE_MODULES: tuple[str, ...] = ("slack_app/send.py",)
MODEL_ENDPOINT_MODULES: tuple[str, ...] = ("core/llm/client.py", "core/llm/gemini.py")


class BoundaryViolation(PermissionError):
    """An action or recipient the boundary refuses. Carries the rule that refused it."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule


def check(action: str, recipient: str = "owner") -> Level:
    """Return the level `action` needs, or raise BoundaryViolation.

    `recipient` is who the output would reach. Level 0 produces no output for anyone, so its
    recipient is not examined. Levels 1 and 2 reach a person, so the recipient must be private.
    """
    if action in NEVER:
        raise BoundaryViolation("never", f"refused: Hearthguard never does this: {NEVER[action]}")
    level = ACTIONS.get(action)
    if level is None:
        raise BoundaryViolation("unlisted", f"refused: {action!r} is not an allowed action")
    if level >= Level.PRIVATE_NOTE and recipient not in PRIVATE_RECIPIENTS:
        rule = "flagged" if recipient == "flagged" else "not_private"
        raise BoundaryViolation(
            rule,
            f"refused: {action!r} may only reach the owner or a named backup, not {recipient!r}",
        )
    return level
