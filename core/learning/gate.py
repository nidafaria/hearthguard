"""The regression gate (docs/HEARTHGUARD.md 8.3, step 4). Pure. No graph, no LLM.

The gate calls the frozen decision code unchanged (core/policy/decision.py: evidence_from_moves
and decide_with_unknowns). It replays the saved red-team suite and the saved real-case rows.

Worst-case replay. An exception that excludes an actor from a move can only remove that move's
firings. The saved suite does not record which actor fired a move, so the replay removes EVERY
firing of the named move at every point. If no planted campaign is lost under that bound, no
campaign can be lost under the real, narrower exception. A campaign is "caught" when any point
decides NOTE or WATCH, the same definition the saved suite uses.

Before the exception is tested, the gate replays the baseline (no exception) and checks that it
reproduces the saved decision at every point. If it does not, the gate refuses to pass.
"""

from dataclasses import asdict, dataclass

from core.learning import templates as tp
from core.policy import decision as dp

CAUGHT = frozenset({"NOTE", "WATCH"})


def lone_keeper(value) -> bool | None:
    """The saved encodings: FLAG_SET / FLAG_NOT_SET / NOT_COMPUTED, or a bool or None."""
    if value in (True, "FLAG_SET"):
        return True
    if value in (False, "FLAG_NOT_SET"):
        return False
    return None


def replay_decision(moves: dict, lk, narrowed: str | None) -> str:
    statuses = dict(moves)
    if narrowed and statuses.get(narrowed) == dp.FIRED:
        statuses[narrowed] = dp.NOT_FIRED  # worst case: every firing of the move is removed
    e = dp.evidence_from_moves(statuses, lk)
    return type(dp.decide_with_unknowns(e)).__name__


@dataclass
class GateResult:
    passed: bool
    reason: str
    baseline_matches_saved: bool
    planted_total: int
    planted_caught_before: int
    planted_caught_after: int
    planted_lost: int
    planted_points_changed: int
    real_total: int
    real_lost: int
    real_points_changed: int

    def as_dict(self) -> dict:
        return asdict(self)


def run(campaigns: list[dict], real_rows: list[dict], template: tp.ExceptionTemplate) -> GateResult:
    narrowed = template.move
    mismatches = 0
    lost = before_c = after_c = changed = 0
    for camp in campaigns:
        was = now = False
        for p in camp["points"]:
            lk = lone_keeper(p["lone_keeper"])
            base = replay_decision(p["moves"], lk, None)
            if base != p["decision"]:
                mismatches += 1
            new = replay_decision(p["moves"], lk, narrowed)
            was |= base in CAUGHT
            now |= new in CAUGHT
            changed += new != base
        before_c += was
        after_c += now
        lost += was and not now

    real_lost = real_changed = 0
    for row in real_rows:
        lk = lone_keeper(row["lone_keeper"])
        base = replay_decision(row["moves"], lk, None)
        new = replay_decision(row["moves"], lk, narrowed)
        real_changed += new != base
        real_lost += base in CAUGHT and new not in CAUGHT

    baseline_ok = mismatches == 0
    if not baseline_ok:
        reason = f"baseline replay differs from the saved decision at {mismatches} points"
    elif lost:
        reason = f"{lost} planted campaign(s) lost"
    elif real_lost:
        reason = f"{real_lost} real-case detection(s) lost"
    else:
        reason = "no planted campaign or real-case detection lost"
    return GateResult(
        passed=baseline_ok and lost == 0 and real_lost == 0,
        reason=reason,
        baseline_matches_saved=baseline_ok,
        planted_total=len(campaigns),
        planted_caught_before=before_c,
        planted_caught_after=after_c,
        planted_lost=lost,
        planted_points_changed=changed,
        real_total=len(real_rows),
        real_lost=real_lost,
        real_points_changed=real_changed,
    )
