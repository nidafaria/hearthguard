"""event-stream and axios incident records -> org graphs (spec §3.1, §6.1, §6.6).

  org_event_stream   from the cached npm packument and GitHub issues #115 and #116
  org_axios          from the cached npm packument, plus the two removed malicious versions

Everything written comes from files under data/raw/incidents/ (eval/incidents_fetch.py). Identifiers
are hashed (packs/oss/npm.py, packs/oss/tracker.py). MERGE on unique keys, so a second load changes
nothing. Detectors never read `evidence`; it records where a fact came from for people.

What the registry does and does not say (kept visible in the graph, never filled in):
  - a maintainer listed on a version gets CAN_GRANT npm_publish from the first version that lists
    them. A removal from the list is not modelled (no `until`), so counts after a removal are too
    high; the replays stop at the incident date.
  - the FIRST maintainer's grant predates the registry data and is not written. A maintainer who
    appears later gets a GRANTED edge at the time of the first version that lists them, which is an
    upper bound on the grant time: the registry records no grant event.
  - the removed axios versions have no publisher or path in the registry. Their path comes from one
    SECONDARY write-up that quotes the registry metadata; each fact is stored only if the quoted
    sentence is in the cached file, and the Action carries evidence = 'secondary'.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from packs.oss import npm, tracker

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "incidents"
WRITE_TIMEOUT_MS = 60_000

# Already-public, adjudicated handles that may be named (spec §1 R6, §4.5 rule 7). Everyone else
# is a hash.
EVENT_STREAM_PERSONAS = frozenset({"right9ctrl"})

SECONDARY_SOURCE = "axios/stepsecurity_writeup.html"
# Facts about the removed axios versions, each tied to the sentence that states it.
AXIOS_SECONDARY_FACTS = {
    "channel_npm_user_no_oidc": (
        "published manually via a stolen npm access token with no OIDC binding"
    ),
    "publisher_name": '"_npmUser" : { "name" : "jasonsaayman"',
    "no_tag": "There is no commit or tag in the axios GitHub repository that corresponds to 1.14.1",
}
AXIOS_MALICIOUS = ("1.14.1", "0.30.4")

CASES = {
    "event_stream": {"org": "event_stream", "package": "event-stream"},
    "axios": {"org": "axios", "package": "axios"},
}


def _read_json(name: str, root: Path = RAW):
    return json.loads((root / name).read_text(encoding="utf-8"))


def page_text(name: str, root: Path = RAW) -> str:
    s = (root / name).read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


def secondary_facts(root: Path = RAW) -> dict:
    """Which of the quoted sentences are really in the cached write-up. Raises if one is not."""
    text = page_text(SECONDARY_SOURCE, root)
    # the cached page has a replacement character where the source has an apostrophe or dash
    text = text.replace("�", "'")
    missing = [k for k, q in AXIOS_SECONDARY_FACTS.items() if q.replace("�", "'") not in text]
    if missing:
        raise ValueError(f"quoted sentence not in the cached source: {missing}")
    return dict(AXIOS_SECONDARY_FACTS)


def build(case: str, root: Path = RAW) -> dict:
    """Pure over the cached files: every row the graph needs, for `case`."""
    info = CASES[case]
    packument = _read_json(f"{case}/npm_{info['package']}.json", root)
    personas = EVENT_STREAM_PERSONAS if case == "event_stream" else frozenset()
    parsed = npm.parse_packument(packument, public_personas=personas)
    out = {
        "case": case,
        "org": info["org"],
        "package": info["package"],
        "releases": parsed["releases"],
        "removed": parsed["removed"],
        "maintainer_spans": parsed["maintainer_spans"],
        "personas": dict(parsed["public_personas"]),
        "issues": [],
        "secondary": [],
    }
    if case == "event_stream":
        for n in (115, 116):
            issue = _read_json(f"event_stream/issue_{n}.json", root)
            cpath = root / f"event_stream/issue_{n}_comments.json"
            comments = json.loads(cpath.read_text(encoding="utf-8")) if cpath.is_file() else []
            t = tracker.parse_thread(
                issue, comments, "dominictarr/event-stream", public_personas=personas
            )
            out["issues"] += t["events"]
            out["personas"].update(t["public_personas"])
    if case == "axios":
        facts = secondary_facts(root)
        publisher = npm.npm_hid("jasonsaayman")
        earlier = {r["publisher_hid"] for r in parsed["releases"] if r["publisher_hid"]}
        for r in parsed["removed"]:
            if r["version"] in AXIOS_MALICIOUS:
                out["secondary"].append(
                    {
                        **r,
                        "publisher_hid": publisher,
                        "path": {
                            "channel": "npm_user",
                            "ci": False,
                            "publisher_in_set": publisher in earlier,
                        },
                        "evidence": "secondary",
                        "source": SECONDARY_SOURCE,
                        "facts": sorted(facts),
                    }
                )
    return out


def _all_actors(doc: dict) -> dict[str, dict]:
    first: dict[str, int] = {}

    def see(hid: str | None, at: int) -> None:
        if hid:
            first[hid] = min(at, first.get(hid, at))

    for r in doc["releases"]:
        see(r["publisher_hid"], r["at"])
    for r in doc["secondary"]:
        see(r["publisher_hid"], r["at"])
    for e in doc["issues"]:
        see(e["actor_hid"], e["at"])
    for s in doc["maintainer_spans"]:
        see(s["hid"], s["first_listed_at"])
    ci = {r["publisher_hid"] for r in doc["releases"] if r["publisher_is_ci"]}
    return {
        h: {"hid": h, "first_seen": at, "kind": "bot" if h in ci else "human"}
        for h, at in first.items()
    }


def load(client: FalkorClient, doc: dict, graph: str | None = None) -> dict:
    graph = graph or f"org_{doc['org']}"
    apply_schema(client, graph)

    def q(cypher: str, params: dict | None = None):
        return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    q(
        "MERGE (o:Org {id: $id}) SET o.name = $id, o.pack = 'oss', "
        "o.connected_by = 'public_record'",
        {"id": doc["org"]},
    )
    q("MERGE (:Privilege {kind: 'npm_publish', sensitive: true})")
    actors = _all_actors(doc)
    q(
        "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) "
        "SET a.kind = r.kind, a.first_seen_in_org = r.first_seen",
        {"rows": list(actors.values())},
    )
    if doc["personas"]:
        q(
            "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}) SET a.handle_public = r.handle",
            {"rows": [{"hid": h, "handle": n} for h, n in doc["personas"].items()]},
        )

    def release_rows(rows: list[dict], evidence: str) -> list[dict]:
        return [
            {
                "ref": r["ref"],
                "at": r["at"],
                "hid": r.get("publisher_hid"),
                "pid": r["ref"],
                "props": r["path"],
                "evidence": evidence,
            }
            for r in rows
        ]

    for rows in (
        release_rows(doc["releases"], "npm_registry"),
        release_rows(doc["secondary"], "secondary"),
    ):
        if not rows:
            continue
        q(
            "UNWIND $rows AS r MERGE (x:Action {ref: r.ref}) "
            "SET x.kind = 'release', x.at = r.at, x.evidence = r.evidence "
            "MERGE (p:Path {id: r.pid}) SET p += r.props "
            "MERGE (x)-[:VIA]->(p)",
            {"rows": rows},
        )
        q(
            "UNWIND $rows AS r WITH r WHERE r.hid IS NOT NULL "
            "MATCH (a:Actor {hid: r.hid}), (x:Action {ref: r.ref}) "
            "MERGE (a)-[d:DID]->(x) SET d.at = r.at",
            {"rows": rows},
        )
    # A version the registry lists in `time` but no longer serves: its time is real, its publisher
    # and path are unknown, so it gets an Action and no Path.
    secondary_refs = {r["ref"] for r in doc["secondary"]}
    time_only = [
        {"ref": r["ref"], "at": r["at"]} for r in doc["removed"] if r["ref"] not in secondary_refs
    ]
    if time_only:
        q(
            "UNWIND $rows AS r MERGE (x:Action {ref: r.ref}) "
            "SET x.kind = 'release', x.at = r.at, x.evidence = 'registry_time_only'",
            {"rows": time_only},
        )
    if doc["issues"]:
        q(
            "UNWIND $rows AS r MERGE (x:Action {ref: r.ref}) "
            "SET x.kind = 'issue', x.at = r.at, x.place = r.place",
            {"rows": doc["issues"]},
        )
        q(
            "UNWIND $rows AS r WITH r WHERE r.actor_hid IS NOT NULL "
            "MATCH (a:Actor {hid: r.actor_hid}), (x:Action {ref: r.ref}) "
            "MERGE (a)-[d:DID]->(x) SET d.at = r.at",
            {"rows": doc["issues"]},
        )

    ci = {r["publisher_hid"] for r in doc["releases"] if r["publisher_is_ci"]}
    first_release_at = min((r["at"] for r in doc["releases"]), default=None)
    ref = f"npm:{doc['package']}"
    spans = [s for s in doc["maintainer_spans"] if s["hid"] not in ci]
    q(
        "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}), (p:Privilege {kind: 'npm_publish'}) "
        "MERGE (a)-[c:CAN_GRANT]->(p) "
        "SET c.approvals_required = 1, c.at = r.at, c.evidence_ref = $ref",
        {"rows": [{"hid": s["hid"], "at": s["first_listed_at"]} for s in spans], "ref": ref},
    )
    later = [s for s in spans if s["first_listed_at"] > (first_release_at or 0)]
    if later:
        q(
            "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}), (p:Privilege {kind: 'npm_publish'}) "
            "MERGE (a)-[g:GRANTED {at: r.at, evidence_ref: $ref}]->(p)",
            {"rows": [{"hid": s["hid"], "at": s["first_listed_at"]} for s in later], "ref": ref},
        )
    return counts(client, graph)


def counts(client: FalkorClient, graph: str) -> dict:
    n = client.query(graph, "MATCH (n) RETURN count(n)", timeout_ms=WRITE_TIMEOUT_MS)
    e = client.query(graph, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=WRITE_TIMEOUT_MS)
    return {"nodes": n.result_set[0][0], "edges": e.result_set[0][0]}
