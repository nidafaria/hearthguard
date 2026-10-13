"""Propose, check and classify one learned exception from one dismissal (docs/HEARTHGUARD.md 8.3).

Pure apart from reading the saved files passed in. The graph writes (OwnerDecision, playbook)
happen in the callers, so this module can be unit-tested without FalkorDB.
"""

import hashlib
import json
from pathlib import Path

from core.agents.cases import CASES, RESULTS, normalize_rows, read_json
from core.learning import filler, gate, safety, states
from core.learning import templates as tp

SUITE = "redteam_xz.json"  # the saved 200-campaign red-team suite (block C, seed 7)
REAL_CASES = ("xz", "tallowdate")  # public xz record and the synthetic tallowdate case


def load_suite(results: Path = RESULTS) -> tuple[list[dict], list[dict]]:
    """(planted campaigns, real-case rows). Read from saved files only."""
    campaigns = read_json(results / SUITE)["campaigns"]
    rows: list[dict] = []
    for case_id in REAL_CASES:
        rows.extend(normalize_rows(CASES[case_id], results))
    return campaigns, rows


def exception_id(template: tp.ExceptionTemplate) -> str:
    text = json.dumps(template.canonical(), sort_keys=True)
    return "exc:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def learn(
    reason: str,
    campaigns: list[dict],
    real_rows: list[dict],
    *,
    agreements: int = 1,
    owner_approved: bool = False,
) -> dict:
    """The full path for one dismissal reason. `agreements` counts this dismissal too."""
    proposal = filler.propose(reason)
    template = proposal.template
    if template is None:
        state, why = states.end_state(
            proposed=False,
            violations=[],
            gate=None,
            agreements=agreements,
            owner_approved=owner_approved,
        )
        return {
            "exception_id": None,
            "template": None,
            "state": state,
            "state_reason": why,
            "attempts": proposal.attempts,
            "safety": {"rules": list(safety.RULES), "violations": []},
            "gate": None,
        }
    violations = safety.violations(template)
    result = None if violations else gate.run(campaigns, real_rows, template)
    state, why = states.end_state(
        proposed=True,
        violations=violations,
        gate=result,
        agreements=agreements,
        owner_approved=owner_approved,
    )
    return {
        "exception_id": exception_id(template),
        "template": template.canonical(),
        "state": state,
        "state_reason": why,
        "attempts": proposal.attempts,
        "safety": {"rules": list(safety.RULES), "violations": violations},
        "gate": result.as_dict() if result else None,
    }
