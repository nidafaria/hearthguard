"""Load the synthetic tallowdate case into org_tallowdate (docs/HEARTHGUARD.md §6.1).

Run: uv run python -m redteam.load_tallowdate [--twice]
Reads data/synthetic/tallowdate.json (written by redteam/tallowdate.py) and writes
eval/results/tallowdate_load.json. Same node and edge model as org_xz (packs/oss/xz_graph.py).

Synthetic: every node and edge carries synthetic: true. Only the three fictional people keep a
name. Every other actor is an HMAC of its label with HEARTHGUARD_HASH_SALT. MERGE on unique keys
only, so a second load changes no count.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.graph.client import FalkorClient
from core.graph.hashing import identifier_hash
from core.graph.schema import apply_schema
from packs.oss.xz_graph import BATCH, WRITE_TIMEOUT_MS, _chunks, graph_counts

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "synthetic" / "tallowdate.json"
OUT = ROOT / "eval" / "results" / "tallowdate_load.json"
CASE = "tallowdate"
ORG_ID = "tallowdate"
GRAPH = f"org_{ORG_ID}"
NAMED = frozenset({"Mira", "Tomás", "Rowan"})

# Event kind -> Action kind. A merged PR is recorded as the commit it produced (xz model).
ACTION_KIND = {
    "pr_review": "review",
    "pr_merged": "commit",
    "comment": "comment",
    "issue_opened": "issue",
    "post": "post",
    "account_created": "account_created",
    "role_accepted": "role_accepted",
    "rights_requested": "rights_requested",
    "absence": "absence",
    "release_signed": "release",
}
RELEASE_PATH = {"channel": "git", "verified": False, "approvers": 2}

Q_ORG = (
    "MERGE (o:Org {id: $id}) "
    "SET o.name = $id, o.pack = 'oss', o.connected_by = 'synthetic_case', o.synthetic = true"
)
Q_ACTORS = """UNWIND $rows AS r
MERGE (a:Actor {hid: r.hid})
  SET a.kind = 'human', a.first_seen_in_org = r.first_seen, a.synthetic = true,
      a.planted = r.planted, a.campaign_id = r.campaign_id, a.name = r.name"""
Q_ACTIONS = """UNWIND $rows AS r
MERGE (a:Actor {hid: r.hid})
MERGE (c:Action {ref: r.ref})
  SET c.kind = r.kind, c.at = r.at, c.case = $case, c.synthetic = true,
      c.planted = r.planted, c.campaign_id = r.campaign_id
MERGE (a)-[d:DID]->(c)
  SET d.at = r.at, d.synthetic = true"""
Q_RELEASES = """UNWIND $rows AS r
MERGE (c:Action {ref: r.ref})
MERGE (p:Path {channel: $channel, verified: $verified, approvers: $approvers, synthetic: true})
MERGE (c)-[v:VIA]->(p)
  SET v.synthetic = true"""
Q_FACT_REVIEWS = (
    "MATCH (a:Actor {hid: $hid})-[:DID]->(r:Action {kind: 'review'}) "
    "RETURN count(r) AS n"
)


def _epoch(day: str) -> int:
    y, m, d = (int(x) for x in day.split("-"))
    return int(datetime(y, m, d, tzinfo=UTC).timestamp())


def _hid(label: str) -> str:
    return identifier_hash(label)


def build_rows(case: dict) -> dict[str, Any]:
    """Map the case onto Actor, Action and Path rows. Pure: no database access."""
    actors: dict[str, dict] = {}
    actions: list[dict] = []
    releases: list[dict] = []
    for e in case["events"]:
        label = e["actor"]
        at = _epoch(e["date"])
        planted = bool(e["planted"])
        hid = _hid(label)
        if hid not in actors:
            actors[hid] = {
                "hid": hid,
                "first_seen": at,
                "name": label if label in NAMED else None,
                "planted": planted,
                "campaign_id": e["campaign_id"],
            }
        else:
            actors[hid]["first_seen"] = min(actors[hid]["first_seen"], at)
            actors[hid]["planted"] = actors[hid]["planted"] or planted
        action = {
            "hid": hid,
            "ref": e["id"],
            "kind": ACTION_KIND[e["kind"]],
            "at": at,
            "planted": planted,
            "campaign_id": e["campaign_id"],
        }
        actions.append(action)
        if e["kind"] == "release_signed":
            releases.append({"ref": e["id"]})
    for a in actors.values():
        if a["name"] is not None and a["name"] not in NAMED:
            raise ValueError("a name outside the allowlist reached the loader")
    return {"actors": list(actors.values()), "actions": actions, "releases": releases}


def load(client: FalkorClient, case: dict, graph: str = GRAPH) -> dict[str, Any]:
    rows = build_rows(case)
    apply_schema(client, graph)

    def q(cypher: str, params: dict):
        return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    q(Q_ORG, {"id": ORG_ID})
    for batch in _chunks(rows["actors"], BATCH):
        q(Q_ACTORS, {"rows": batch})
    for batch in _chunks(rows["actions"], BATCH):
        q(Q_ACTIONS, {"rows": batch, "case": CASE})
    rel = rows["releases"]
    for batch in _chunks(rel, BATCH):
        q(Q_RELEASES, {"rows": batch, **RELEASE_PATH})
    return rows


def facts(client: FalkorClient, graph: str = GRAPH) -> dict[str, Any]:
    """Counts the Hearthguard-side demo beats quote. Each is a saved, queried number."""
    hid = _hid("Tomás")
    res = client.query(graph, Q_FACT_REVIEWS, {"hid": hid}, timeout_ms=WRITE_TIMEOUT_MS)
    return {
        "tomas_review_count": {
            "value": res.result_set[0][0],
            "query": Q_FACT_REVIEWS,
            "params": {"hid": "<hashed id of Tomás, not written>"},
            "query_ms": res.run_time_ms,
            "synthetic": True,
        }
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--twice", action="store_true", help="load twice and compare the counts")
    args = ap.parse_args(argv)

    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    client = FalkorClient()
    load(client, case)
    run1 = graph_counts(client, GRAPH)
    run2 = None
    if args.twice:
        load(client, case)
        run2 = graph_counts(client, GRAPH)
        if run2 != run1:
            print("FAIL: counts changed on the second run", file=sys.stderr)
            return 1

    doc = {
        "synthetic": True,
        "case": CASE,
        "label": "SYNTHETIC: fictional project, fictional people",
        "graph": GRAPH,
        "source": "data/synthetic/tallowdate.json",
        "events_in_source": len(case["events"]),
        "counts_after_run_1": run1,
        "counts_after_run_2": run2,
        "idempotent": (run2 == run1) if run2 is not None else None,
        "queries": {
            "org": Q_ORG,
            "actors": Q_ACTORS,
            "actions": Q_ACTIONS,
            "releases": Q_RELEASES,
        },
        "release_path": RELEASE_PATH,
        "facts": facts(client, GRAPH),
        "note": (
            "Hashed ids are not written. Only Mira, Tomás and Rowan keep a name, each marked "
            "synthetic. Path.verified is false: no release signature exists in this case."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"nodes={run1['nodes']}")
    print(f"edges={run1['edges']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
