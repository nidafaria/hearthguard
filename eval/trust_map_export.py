"""Export the trust map graph for the screen: eval/results/trust_map_tallowdate.json.

Run: uv run python -m eval.trust_map_export     (needs FalkorDB with org_tallowdate loaded)
Reads org_tallowdate with explicit timeouts. Exports hashed actor ids only: no names, no emails, no
persona fields. Every node and edge is labelled synthetic, because the graph is the synthetic
tallowdate case. A trust path is written only when the saved results name one; the release path
in eval/results/tallowdate_load.json has no actor sequence, so none is written.
"""

import json
from pathlib import Path

from core.graph.client import FalkorClient

GRAPH = "org_tallowdate"
TIMEOUT_MS = 10_000
RESULTS = Path(__file__).resolve().parent / "results"
OUT = RESULTS / "trust_map_tallowdate.json"
LABEL = "SYNTHETIC: fictional project, fictional people. Hashed actor ids. Not a finding."

ACTORS = "MATCH (a:Actor) OPTIONAL MATCH (a)-[:DID]->(c:Action) RETURN a.hid, count(c) LIMIT 1000"
RELEASES = (
    "MATCH (r:Action {kind: 'release'}) OPTIONAL MATCH (r)-[:VIA]->(p:Path) "
    "RETURN r.ref, p.channel, p.verified LIMIT 1000"
)
ACTOR_RELEASE = (
    "MATCH (a:Actor)-[:DID]->(r:Action {kind: 'release'}) RETURN a.hid, r.ref LIMIT 1000"
)


def build(client: FalkorClient) -> dict:
    nodes, edges = [], []
    for hid, n in client.query(GRAPH, ACTORS, timeout_ms=TIMEOUT_MS).result_set:
        nodes.append({"id": f"actor:{hid}", "type": "actor", "actions": n, "synthetic": True})
    for ref, channel, verified in client.query(GRAPH, RELEASES, timeout_ms=TIMEOUT_MS).result_set:
        nodes.append({"id": f"release:{ref}", "type": "release", "synthetic": True})
        nodes.append({"id": f"path:{channel}:{verified}", "type": "path", "synthetic": True})
        edges.append(
            {
                "source": f"release:{ref}",
                "target": f"path:{channel}:{verified}",
                "type": "VIA",
                "synthetic": True,
            }
        )
    for hid, ref in client.query(GRAPH, ACTOR_RELEASE, timeout_ms=TIMEOUT_MS).result_set:
        edges.append(
            {"source": f"actor:{hid}", "target": f"release:{ref}", "type": "DID", "synthetic": True}
        )
    # Unique nodes, keeping the first occurrence.
    seen, unique = set(), []
    for node in nodes:
        if node["id"] not in seen:
            seen.add(node["id"])
            unique.append(node)
    return {
        "synthetic": True,
        "label": LABEL,
        "graph": GRAPH,
        "nodes": unique,
        "edges": edges,
        "trust_path": None,
        "trust_path_note": (
            "No trust path in the saved results. tallowdate_load.json records the release path "
            "(channel, verified, approver count) but no actor sequence, so none is highlighted."
        ),
        "hashed_ids_only": True,
    }


def main() -> int:
    doc = build(FalkorClient())
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(doc['nodes'])} nodes, {len(doc['edges'])} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
