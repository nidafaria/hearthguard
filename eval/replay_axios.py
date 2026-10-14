"""Replay of axios (Mar 2026, Bypass only) on org_axios (spec §3.1, §10.2).

  FALKORDB_PORT=<port> uv run python -m eval.replay_axios

Needs the graph from eval/incidents_load.py. Writes eval/results/replay_axios.json. Two runs:
  with_secondary_record  the graph as loaded: the two removed versions carry the path that one
                         SECONDARY write-up quotes from the registry (published by the lead
                         maintainer's account with no OIDC binding). Labelled secondary.
  registry_only          the same graph with those two paths and publishers removed, which is all
                         the primary record (registry `time` and the OSV advisory) supports.
                         Expect Bypass NOT_COMPUTED here: the registry no longer serves the path.
Times: e0 is axios@1.14.0 (the last release before the incident); the malicious release is
axios@1.14.1; the public report is axios/axios issue #10604. All come from data/raw/incidents/.
"""

from __future__ import annotations

import sys
import uuid

from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from eval import incidents_replay as rp
from packs.oss import incidents_graph as ig
from packs.oss import npm, tracker

RAW = ig.RAW


def times(root=RAW) -> dict:
    pk = rp.read_json(root, "axios/npm_axios.json")
    return {
        "e0": npm.epoch(pk["time"]["1.14.0"]),
        "malicious": npm.epoch(pk["time"]["1.14.1"]),
        "report": tracker.epoch(rp.read_json(root, "axios/issue_10604.json")["created_at"]),
    }


def registry_only_copy(client: FalkorClient, source_org: str) -> str:
    """A copy of org_<source> where the secondary-sourced releases keep only their time."""
    org = "axiosreg" + uuid.uuid4().hex[:8]
    graph = f"org_{org}"
    client.drop(graph)
    client.copy(f"org_{source_org}", graph)
    for cypher in (
        "MATCH (:Action {evidence: 'secondary'})-[:VIA]->(p:Path) DETACH DELETE p",
        "MATCH ()-[d:DID]->(x:Action {evidence: 'secondary'}) DELETE d",
        "MATCH (x:Action {evidence: 'secondary'}) SET x.evidence = 'registry_time_only'",
    ):
        client.query(graph, cypher, timeout_ms=60_000)
    return org


Q_CHANNELS = (
    "MATCH (x:Action {kind: 'release'})-[:VIA]->(p:Path) "
    "WHERE x.at < $T AND x.at > $T - $w AND x.evidence = 'npm_registry' "
    "RETURN p.channel AS channel, count(x) AS n ORDER BY channel LIMIT 20"
)


def channel_windows(client: FalkorClient, org: str, t_malicious: int) -> dict:
    """Release channels before the malicious release, by trailing window. NOT a detector: the
    frozen Bypass keeps its 730-day window; this shows how much that window matters."""
    out = {}
    for days in (730, 180, 90):
        rows = run_as_of(
            client, f"org_{org}", Q_CHANNELS, {"T": t_malicious, "w": days * rp.DAY_S}
        ).result_set
        out[f"trailing_{days}d"] = {str(c): int(n) for c, n in rows}
    return out


def run(client: FalkorClient | None = None, root=RAW) -> dict:
    client = client or FalkorClient()
    t = times(root)
    sources = [
        "data/raw/incidents/axios/npm_axios.json",
        "data/raw/incidents/axios/osv_MAL-2026-2307.json",
        "data/raw/incidents/axios/issue_10604.json",
    ]
    with_secondary = rp.replay_graph(
        client,
        "axios",
        t["e0"],
        t["report"],
        t["malicious"],
        [*sources, "data/raw/incidents/axios/stepsecurity_writeup.html (SECONDARY)"],
    )
    reg = registry_only_copy(client, "axios")
    try:
        registry_only = rp.replay_graph(client, reg, t["e0"], t["report"], t["malicious"], sources)
    finally:
        client.drop(f"org_{reg}")
    registry_only["graph"] = "org_axios (copy, secondary paths removed)"
    notes = [
        "Bypass did not fire. Channel and CI match the remembered normal because 33 of the 37 "
        "releases in the trailing 730 days were manual publishes; the four trusted-publisher "
        "releases are recent. Provenance, verified, key and artifact-vs-tag are not recorded for "
        "the removed versions, so those properties are NOT_COMPUTED.",
        "The path of the removed versions comes from one secondary write-up; the registry no "
        "longer serves them (registry_only shows what the primary record alone supports).",
        "This is an unflattering result for the frozen 730-day window: it is published as is.",
    ]
    return rp.envelope(
        "axios (Mar 2026, Bypass only)",
        t["e0"],
        t["report"],
        t["malicious"],
        {
            "with_secondary_record": with_secondary,
            "registry_only": registry_only,
            "release_channels_before_incident": {
                "counts_by_window": channel_windows(client, "axios", t["malicious"]),
                "note": "Descriptive only, not a detector. The frozen Bypass remembers 730 days; "
                "if most releases in that window were manual publishes, a manual publish "
                "matches the remembered normal. Compare the shorter windows.",
            },
        },
        notes,
    )


def main() -> int:
    doc = run()
    path = rp.write(doc, "replay_axios.json")
    print(f"wrote {path}")
    for name in ("with_secondary_record", "registry_only"):
        r = doc[name]
        print(name, "fired:", r["fired"], r["first_fire_utc"], r["lead_time_days_to_public_report"])
        for p in r["points"]:
            print(
                "  ",
                p["at_utc"],
                p["moves"],
                p["decision"],
                p["takeover_cost"]["value"],
                p["guardians"]["value"],
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
