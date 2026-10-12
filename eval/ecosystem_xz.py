"""`make ecosystem-xz`: fetch, parse, load ecosystem_xz twice, compute visibility gaps.

Writes eval/results/ecosystem_sources.json, ecosystem_events.json, ecosystem_load.json and
ecosystem_gaps.json. No model is called. The graph is dropped first so the counts start from zero,
then loaded twice to show the second load changes nothing.
"""

import json
from pathlib import Path

from core.graph.client import FalkorClient
from packs.oss.ecosystem import fetch, gaps, parse
from packs.oss.ecosystem import graph as G

RESULTS = Path(__file__).resolve().parent / "results"


def write(name: str, obj: dict) -> None:
    (RESULTS / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    sources = fetch.run()
    write("ecosystem_sources.json", sources)

    events, cut = parse.all_events()
    reg = parse.build_registry(events)
    rows = parse.event_rows(events, reg)
    write(
        "ecosystem_events.json",
        {
            "cutoff": parse.CUTOFF.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "events_after_cutoff_not_included": cut,
            "role_evidence": parse.ROLE_EVIDENCE,
            "events": rows,
        },
    )

    client = FalkorClient()
    client.drop(G.GRAPH)
    G.load(client, events, reg)
    first = G.counts(client)
    G.load(client, events, reg)
    second = G.counts(client)
    write(
        "ecosystem_load.json",
        {
            "graph": G.GRAPH,
            "after_first_load": first,
            "after_second_load": second,
            "identical": first == second,
            "events_loaded": len(rows),
        },
    )

    result = gaps.run_all(client, events, reg)
    write("ecosystem_gaps.json", result)

    fetched = [s["id"] for s in sources["sources"] if s["status"] == 200]
    print("core sources fetched:", len(fetched), "of", len(sources["sources"]))
    print("nodes", second["node_total"], second["nodes"])
    print("edges", second["edge_total"], second["edges"])
    print("identical on reload:", first == second)
    print(
        "decisions computed",
        result["decisions_computed"],
        "not computed",
        result["decisions_not_computed"],
        "gap rows",
        result["gap_rows"],
    )
    return 0 if first == second else 1


if __name__ == "__main__":
    raise SystemExit(main())
