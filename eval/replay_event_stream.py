"""Replay of event-stream (2018) on org_event_stream (spec §3.1, §10.2).

  FALKORDB_PORT=<port> uv run python -m eval.replay_event_stream

Needs the graph from eval/incidents_load.py. Writes eval/results/replay_event_stream.json.
Times: e0 is the last release by the original maintainer (3.3.4); the malicious release is
event-stream@3.3.6 (time from the registry, removed since); the public report is GitHub issue
dominictarr/event-stream#115. All three come from the cached files in data/raw/incidents/.
"""

from __future__ import annotations

import sys

from core.graph.client import FalkorClient
from eval import incidents_replay as rp
from packs.oss import incidents_graph as ig
from packs.oss import npm, tracker

RAW = ig.RAW


def times(root=RAW) -> dict:
    pk = rp.read_json(root, "event_stream/npm_event-stream.json")
    return {
        "e0": npm.epoch(pk["time"]["3.3.4"]),
        "malicious": npm.epoch(pk["time"]["3.3.6"]),
        "report": tracker.epoch(rp.read_json(root, "event_stream/issue_115.json")["created_at"]),
    }


def run(client: FalkorClient | None = None, root=RAW) -> dict:
    client = client or FalkorClient()
    t = times(root)
    body = rp.replay_graph(
        client,
        "event_stream",
        t["e0"],
        t["report"],
        t["malicious"],
        [
            "data/raw/incidents/event_stream/npm_event-stream.json",
            "data/raw/incidents/event_stream/issue_115.json",
            "data/raw/incidents/event_stream/osv_GHSA-mh6f-8j2x-4483.json",
        ],
    )
    notes = [
        "Bypass at event-stream@3.3.5 is NOT_COMPUTED: the previous release (3.3.4) is more than "
        "730 days earlier, so the remembered normal has expired (a two-year gap).",
        "event-stream@3.3.6, the malicious release, was removed from the registry: its time is "
        "recorded, its publisher and path are not, so Bypass cannot judge it.",
        "The Bypass FIRED at 4.0.0 compares it with a normal of one release, 3.3.5, which was "
        "itself the new publisher's first. It fires because 4.0.0 differs from that one release "
        "on publisher_in_set, not because it differs from the original maintainer's history.",
        "The first NOTE is therefore after the malicious release; the earlier points are HOLD "
        "(one move fired, another unknown).",
    ]
    return rp.envelope(
        "event-stream (2018)", t["e0"], t["report"], t["malicious"], {"replay": body}, notes
    )


def main() -> int:
    doc = run()
    path = rp.write(doc, "replay_event_stream.json")
    r = doc["replay"]
    print(f"wrote {path}")
    for p in r["points"]:
        print(
            p["at_utc"],
            p["moves"],
            p["lone_keeper"],
            p["decision"],
            p["takeover_cost"]["value"],
            p["guardians"]["value"],
        )
    print(
        "fired:",
        r["fired"],
        r["first_fire_utc"],
        r["lead_time_days_to_malicious_release"],
        r["lead_time_days_to_public_report"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
