"""The strict exception template (docs/HEARTHGUARD.md 8.3, step 2). Pure. No graph, no LLM.

A learned exception is never free-form code. It is three fields drawn from fixed building blocks:
`applies_to` (one real move), `when` (up to two clauses from BLOCKS, joined by AND) and `effect`
(one literal value). extra="forbid" means a template cannot carry a takeover-cost, guardian or
any other field (8.3 safety rule 3).

The playbook copy holds exactly these fields. It holds no org id and no note id (spec 6.5).
"""

import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from core.policy.decision import MOVES

EFFECT = "exclude_actor_from_move"
# The fixed clause vocabulary. A `when` is valid only if every clause is one of these strings.
BLOCKS = frozenset(
    {
        "actor.kind == 'bot'",
        "actor.hid IN org.declared_bots",
        "actor.hid IN org.declared_handover",
        "actor.hid IN org.declared_contacts",
    }
)
DECLARED = " IN org.declared_"  # a checkable condition names a list the owner declared
MAX_CLAUSES = 2
NAME = re.compile(r"^[a-z][a-z_]{2,39}$")


class ExceptionTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exception: str = Field(pattern=NAME.pattern)
    applies_to: str
    when: str = Field(min_length=1, max_length=300)
    effect: str

    @field_validator("applies_to")
    @classmethod
    def _real_move(cls, v: str) -> str:
        head, _, move = v.partition(".")
        if head != "move" or move not in MOVES:
            raise ValueError(f"applies_to must be move.<one of {MOVES}>, got {v!r}")
        return v

    @field_validator("effect")
    @classmethod
    def _literal_effect(cls, v: str) -> str:
        if v != EFFECT:
            raise ValueError(f"effect must be {EFFECT!r}, got {v!r}")
        return v

    @field_validator("when")
    @classmethod
    def _building_blocks(cls, v: str) -> str:
        clauses = [c.strip() for c in v.split(" AND ")]
        if len(clauses) > MAX_CLAUSES:
            raise ValueError(f"at most {MAX_CLAUSES} clauses, got {len(clauses)}")
        bad = [c for c in clauses if c not in BLOCKS]
        if bad:
            raise ValueError(f"clauses outside the building blocks: {bad}")
        if not any(DECLARED in c for c in clauses):
            raise ValueError("no checkable condition: a clause must name a declared list")
        return v

    @property
    def move(self) -> str:
        return self.applies_to.partition(".")[2]

    def canonical(self) -> dict:
        return {
            "exception": self.exception,
            "applies_to": self.applies_to,
            "when": self.when,
            "effect": self.effect,
        }


def validate(raw: dict) -> tuple[ExceptionTemplate | None, str | None]:
    """(template, None) if the raw fields are a valid template, else (None, the reason)."""
    try:
        return ExceptionTemplate.model_validate(raw), None
    except ValidationError as e:
        return None, "; ".join(err["msg"] for err in e.errors())
