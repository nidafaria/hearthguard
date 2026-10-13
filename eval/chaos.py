"""Chaos for learning (docs/HEARTHGUARD.md 10.2): inject a random benign pattern, dismiss it, and
run the learning step on it. Pure; no graph, no LLM.

Usage:  uv run python -m eval.chaos --seed 7
        (make chaos SEED=<any>, once the lead wires the target)

The seed picks one benign pattern (bots, a company team handover, a vendor's real contact
change) and a synthetic actor name for it. Every name is made up here and marked synthetic.
Writes eval/results/learning_chaos_seed<seed>.json. The claim tested: zero planted campaigns
lost by any exception that reaches an end state other than Rejected.
"""

import argparse
import json
import random
from pathlib import Path

from core.learning import pipeline as pl
from core.learning import states

RESULTS = Path(__file__).resolve().parent / "results"
PATTERNS = (
    {
        "name": "bots",
        "reason": "these are our CI bots: {actor} and renovate",
    },
    {
        "name": "company_handover",
        "reason": "this was our announced handover of {actor} to the company team",
    },
    {
        "name": "vendor_contact_change",
        "reason": "the vendor's real contact changed; {actor} is their new contact",
    },
)


def inject(seed: int) -> dict:
    """The benign pattern and its dismissal text for one seed. Synthetic names only."""
    rng = random.Random(seed)
    pattern = PATTERNS[rng.randrange(len(PATTERNS))]
    actor = f"synthetic-{rng.randrange(10_000, 99_999)}"
    return {
        "seed": seed,
        "pattern": pattern["name"],
        "synthetic": True,
        "dismissal_reason": pattern["reason"].format(actor=actor),
    }


def run(seed: int, campaigns: list[dict], real_rows: list[dict]) -> dict:
    case = inject(seed)
    out = pl.learn(case["dismissal_reason"], campaigns, real_rows)
    gate = out["gate"]
    return {
        **case,
        "state": out["state"],
        "state_reason": out["state_reason"],
        "exception_id": out["exception_id"],
        "template": out["template"],
        "planted_lost": gate["planted_lost"] if gate else None,
        "planted_total": gate["planted_total"] if gate else None,
        "gate_passed": gate["passed"] if gate else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    campaigns, real_rows = pl.load_suite()
    result = run(args.seed, campaigns, real_rows)
    # Any exception that is kept (Shadow or Adopted) must have lost nothing at the gate.
    kept = result["state"] in (states.SHADOW, states.ADOPTED)
    result["zero_planted_lost_among_kept"] = (not kept) or result["planted_lost"] == 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"learning_chaos_seed{args.seed}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"seed {args.seed}: {result['pattern']} -> {result['state']} "
        f"({result['planted_lost']} planted lost) -> {path.name}"
    )
    return 0 if result["zero_planted_lost_among_kept"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
