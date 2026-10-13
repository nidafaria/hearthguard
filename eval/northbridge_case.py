"""Northbridge / Kestrel finance case, scripted (docs/HEARTHGUARD.md §11.1). Synthetic data only.

Run: uv run python -m eval.northbridge_case
Loads data/synthetic/northbridge.json through the finance pack (parse -> mapping) into
`org_<org>` twice, at two horizons, then runs the same core detectors the OSS pack uses:

  T_BEFORE_LEAVE  2025-09-07, the day before the controller's leave notice
  T_CASE          2025-09-17, the day of the bank-detail change

Computed here, all by core code with no LLM: Rush (the planted contact's change rights came 35
days after his first action; the org's own p10 is the threshold), Bypass (the Sep 17 bank-detail
change against the remembered normal path), Lone keeper, takeover cost, guardians, and the
hardening step "restore two-person approval" run on a GRAPH.COPY (the real graph is untouched).

NOT computed here: Pressure and Vouch. They read claims, and claims come from the Reader, which is
an LLM. The Reader has not been run on this case, so both are reported NOT COMPUTED, as the
tallowdate case does. The Liaison's note is also not generated (it is an LLM step).

Writes eval/results/finance_northbridge_case.json. Timings are left out so the file is stable.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

from core.detectors.bypass import bypass
from core.detectors.lone_keeper import lone_keeper
from core.detectors.rush import rush
from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from packs.finance import mapping, parse, synthetic

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic" / "northbridge.json"
RESULT = ROOT / "eval" / "results" / "finance_northbridge_case.json"

T_BEFORE_LEAVE = parse.to_epoch("2025-09-07T23:59:59Z")
T_CASE = parse.to_epoch("2025-09-17T23:59:59Z")
ATTACK_ACTION = "northbridge:erp:bc-k01"
CONTROL_ACTION = "northbridge:erp:bc-0008"
PRIV_BANK = "bank_change"
PRIV_EDIT = "vendor_edit"
TIMEOUT = 30_000
NOT_COMPUTED_READER = "reader not run on the finance case (claims need the LLM)"


def load_dataset(path: Path = DATA) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def _slim(res) -> dict:
    """A detector result without its queries and timings."""
    d = res.as_dict()
    return {k: d[k] for k in ("detector", "status", "reason", "evidence", "flag") if k in d}


def measure(client: FalkorClient, org: str, T: int) -> dict:
    c = cost.takeover_cost(client, org, PRIV_BANK, T, TIMEOUT)
    g = guardians.guardians(client, org, PRIV_BANK, T, TIMEOUT)
    return {
        "takeover_cost": c.cost,
        "takeover_cost_status": c.status,
        "guardians": g.guardians,
        "guardians_status": g.status,
    }


def harden_two_approvals(client: FalkorClient, org: str, T: int, run: str) -> dict:
    """Restore two-person approval on a copy of org_<org> and re-measure. Original is untouched."""
    original, harden, evaluated = f"org_{org}", f"harden_{run}", f"org_{org}h{run}"
    for g in (harden, evaluated):
        client.drop(g)
    try:
        before = measure(client, org, T)
        client.copy(original, harden)
        client.query(
            harden,
            "MATCH (:Actor)-[e:CAN_GRANT]->(:Privilege {kind: $k}) "
            "SET e.approvals_required = CASE WHEN e.approvals_required >= 2 "
            "THEN e.approvals_required ELSE 2 END",
            {"k": PRIV_BANK},
            timeout_ms=TIMEOUT,
        )
        client.copy(harden, evaluated)
        after = measure(client, f"{org}h{run}", T)
    finally:
        for g in (harden, evaluated):
            client.drop(g)
    return {"step": "require_two_approvals", "before": before, "after": after}


def run(client: FalkorClient, org: str = mapping.ORG_ID, data: Path = DATA) -> dict:
    salt = parse.default_salt()
    parsed = parse.parse_records(load_dataset(data), salt)
    planted_hid = parse.hid(synthetic.DANIEL, salt)
    control_hid = parse.hid(synthetic.HISTORY_CONTACTS[0][0], salt)
    graph = f"org_{org}"
    client.drop(graph)
    try:
        loaded_before = mapping.load(client, graph, parsed, T_BEFORE_LEAVE, org)
        before_leave = measure(client, org, T_BEFORE_LEAVE)
        client.drop(graph)
        loaded = mapping.load(client, graph, parsed, T_CASE, org)
        at_case = measure(client, org, T_CASE)
        moves = {
            "rush": _slim(rush(client, org, PRIV_EDIT, planted_hid, T_CASE, TIMEOUT)),
            "bypass": _slim(bypass(client, org, ATTACK_ACTION, T_CASE, TIMEOUT)),
            "lone_keeper": _slim(lone_keeper(client, org, PRIV_BANK, T_CASE, TIMEOUT)),
            "pressure": {"status": "NOT COMPUTED", "reason": NOT_COMPUTED_READER},
            "vouch": {"status": "NOT COMPUTED", "reason": NOT_COMPUTED_READER},
        }
        controls = {
            "rush_on_a_normal_contact": _slim(
                rush(client, org, PRIV_EDIT, control_hid, T_CASE, TIMEOUT)
            ),
            "bypass_on_a_normal_bank_change": _slim(
                bypass(client, org, CONTROL_ACTION, T_CASE, TIMEOUT)
            ),
        }
        edges_before = client.query(
            graph, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=TIMEOUT
        ).result_set[0][0]
        hardening = harden_two_approvals(client, org, T_CASE, uuid.uuid4().hex[:8])
        edges_after = client.query(
            graph, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=TIMEOUT
        ).result_set[0][0]
    finally:
        client.drop(graph)
    return {
        "case": "northbridge",
        "synthetic": True,
        "spec": "docs/HEARTHGUARD.md §11.1",
        "rule": "docs/decisions/0001-outsider-edges.md (PROPOSED, provisional)",
        "pack": "finance",
        "horizons": {"before_leave": T_BEFORE_LEAVE, "case": T_CASE},
        "loaded_before_leave": loaded_before,
        "loaded_at_case": loaded,
        "before_leave": before_leave,
        "at_case": at_case,
        "moves": moves,
        "controls": controls,
        "hardening": hardening,
        "org_graph_edge_count_before_hardening": edges_before,
        "org_graph_edge_count_after_hardening": edges_after,
        "not_computed": [
            "pressure and vouch (the Reader is an LLM and has not been run on this case)",
            "the Liaison note (an LLM step)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default=mapping.ORG_ID, help="org id; the graph is org_<id>")
    ap.add_argument("--out", default=str(RESULT))
    args = ap.parse_args(argv)
    out = run(FalkorClient(), args.org)
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, m in out["moves"].items():
        print(f"{name:<12} {m['status']}")
    h = out["hardening"]
    print(
        f"takeover cost {h['before']['takeover_cost']} -> {h['after']['takeover_cost']} "
        f"after {h['step']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
