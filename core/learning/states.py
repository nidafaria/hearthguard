"""The four end states of a learned exception (docs/HEARTHGUARD.md 8.3, step 5). Pure.

Adopted      acts. Reached only by owner approval or K independent agreements.
Shadow       records what it WOULD have suppressed, and acts on nothing. The default for an
             exception that passed the gate.
Human review the filler found no building block after its attempts; a human writes it.
Rejected     failed a safety rule or lost a detection at the gate. Kept with its reason.

A valid exception is never discarded silently, and nothing untested ever acts.
"""

from core.learning import gate as gt

ADOPTED = "Adopted"
SHADOW = "Shadow"
HUMAN_REVIEW = "Human review"
REJECTED = "Rejected"
STATES = (ADOPTED, SHADOW, HUMAN_REVIEW, REJECTED)
K_AGREEMENTS = 3  # K from 8.3 step 5. Agreements are dismissals that proposed the same template.


def end_state(
    *,
    proposed: bool,
    violations: list[str],
    gate: gt.GateResult | None,
    agreements: int,
    owner_approved: bool,
) -> tuple[str, str]:
    if not proposed:
        return (
            HUMAN_REVIEW,
            "no building block matched after the filler's attempts; a human writes it",
        )
    if violations:
        return REJECTED, "safety rule: " + "; ".join(violations)
    if gate is None or not gate.passed:
        return REJECTED, "gate: " + (gate.reason if gate else "not run")
    if owner_approved:
        return ADOPTED, "owner approved after passing the gate"
    if agreements >= K_AGREEMENTS:
        return ADOPTED, f"{agreements} independent agreements (K = {K_AGREEMENTS})"
    return (
        SHADOW,
        f"passed the gate; records what it would suppress until K = {K_AGREEMENTS} "
        "agreements or owner approval",
    )
