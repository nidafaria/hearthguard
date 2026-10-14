"""Load the cached event-stream and axios incident records into org graphs (spec §3.1, §6.1).

  FALKORDB_PORT=<port> uv run python -m eval.incidents_load

Needs data/raw/incidents/ (eval/incidents_fetch.py). Builds org_event_stream and org_axios with
packs/oss/incidents_graph.py, loads each TWICE and records that the second load changed no count,
and scans every node and edge property for an email address. Writes
eval/results/incidents_load.json. No LLM, no network.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from core.graph.client import FalkorClient
from packs.oss import incidents_graph as ig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "incidents_load.json"
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")


def email_hits(client: FalkorClient, graph: str) -> list[str]:
    """Locations (never values) where a property holds something shaped like an email address."""
    hits = set()
    for kind, cypher in (("node", "MATCH (n) RETURN n"), ("edge", "MATCH ()-[r]->() RETURN r")):
        for (entity,) in client.query(graph, cypher, timeout_ms=ig.WRITE_TIMEOUT_MS).result_set:
            label = getattr(entity, "labels", None) or [getattr(entity, "relation", "?")]
            for key, value in entity.properties.items():
                if EMAIL.search(str(value)):
                    hits.add(f"{kind}:{label[0]}.{key}")
    return sorted(hits)


def label_counts(client: FalkorClient, graph: str) -> dict:
    nodes = client.query(
        graph, "MATCH (n) RETURN labels(n)[0], count(n) ORDER BY labels(n)[0]", timeout_ms=60_000
    ).result_set
    edges = client.query(
        graph, "MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY type(r)", timeout_ms=60_000
    ).result_set
    return {"nodes": dict(nodes), "edges": dict(edges)}


def run(client: FalkorClient | None = None) -> dict:
    client = client or FalkorClient()
    cases = {}
    for case in ig.CASES:
        doc = ig.build(case)
        graph = f"org_{doc['org']}"
        first = ig.load(client, doc)
        second = ig.load(client, doc)
        cases[case] = {
            "graph": graph,
            "package": doc["package"],
            "releases_in_registry": len(doc["releases"]),
            "removed_versions": [r["ref"] for r in doc["removed"]],
            "secondary_records": [
                {"ref": r["ref"], "evidence": r["evidence"], "source": r["source"]}
                for r in doc["secondary"]
            ],
            "issue_events": len(doc["issues"]),
            "maintainers_listed": len(doc["maintainer_spans"]),
            "named_public_handles": sorted(doc["personas"].values()),
            "counts_after_load_1": first,
            "counts_after_load_2": second,
            "idempotent": first == second,
            "by_label": label_counts(client, graph),
            "email_like_properties": email_hits(client, graph),
        }
    return {
        "scope": "public records only: npm registry, OSV, GitHub issues, one secondary write-up "
        "(labelled). Identifiers hashed; only the adjudicated handle right9ctrl is named.",
        "limits": [
            "CAN_GRANT npm_publish starts at the first version that lists a maintainer; a removal "
            "from the list is not modelled.",
            "The registry records no grant event; a GRANTED edge's time is the first version "
            "listing the maintainer, an upper bound.",
            "The removed axios versions have no registry record; their path is from one secondary "
            "write-up, stored only where the quoted sentence is in the cached file.",
        ],
        "cases": cases,
    }


def main() -> int:
    doc = run()
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for name, c in doc["cases"].items():
        print(
            name,
            c["counts_after_load_1"],
            "idempotent" if c["idempotent"] else "NOT idempotent",
            "email-like:",
            c["email_like_properties"],
        )
    return (
        0
        if all(c["idempotent"] and not c["email_like_properties"] for c in doc["cases"].values())
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
