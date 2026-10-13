"""Safety rules for a learned exception (docs/HEARTHGUARD.md 8.3, step 3). Pure.

Every rule is checked on every proposal, not only on the ones the filler built. A violation
means the exception is Rejected (templates.py has already refused anything outside the schema).
"""

from core.learning import templates as tp

RULES = (
    "never narrows Bypass",
    "suppresses at most one move",
    "never changes takeover cost or guardians",
    "names a concrete, checkable condition",
)


def violations(t: tp.ExceptionTemplate) -> list[str]:
    out: list[str] = []
    if t.move == "BYPASS":
        out.append("never narrows Bypass: path changes always surface")
    # applies_to is one value, so one move. Re-checked here so a schema change cannot drop it.
    if t.applies_to.count(".") != 1:
        out.append("suppresses more than one move")
    # extra="forbid" and the literal effect already keep takeover cost and guardians out. This
    # re-check names the rule in the result if someone loosens the schema later.
    if set(t.canonical()) - {"exception", "applies_to", "when", "effect"}:
        out.append("carries a field that could change takeover cost or guardians")
    clauses = [c.strip() for c in t.when.split(" AND ")]
    if not any(tp.DECLARED in c for c in clauses):
        out.append("no concrete, checkable condition (a declared list must be named)")
    if any(c not in tp.BLOCKS for c in clauses):
        out.append("condition is outside the building blocks")
    return out
