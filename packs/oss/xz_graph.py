"""Map parsed xz git records onto the org graph (docs/HEARTHGUARD.md §6.1).

MERGE on unique keys only.

Idempotent: running load() again over the same input changes no node or edge count.
No Privilege nodes and no grant edges are written: git has no grant record (see
eval/results/xz_grants_unknown.json). No takeover cost, guardians or OUTSIDER node here.
"""

from collections.abc import Iterator
from typing import Any

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema

ORG_ID = "xz"
GRAPH = f"org_{ORG_ID}"
BATCH = 500
WRITE_TIMEOUT_MS = 60_000


def _chunks(rows: list[Any], size: int = BATCH) -> Iterator[list[Any]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def first_seen_map(commits: list[dict], tags: list[dict]) -> dict[str, int]:
    """Earliest event time per hashed actor, over commits authored and tags made."""
    seen: dict[str, int] = {}
    for c in commits:
        seen[c["hid"]] = min(c["at"], seen.get(c["hid"], c["at"]))
    for t in tags:
        if t["kind"] == "annotated" and t["tagger_hid"]:
            seen[t["tagger_hid"]] = min(t["at"], seen.get(t["tagger_hid"], t["at"]))
    return seen


def load(
    client: FalkorClient,
    commits: list[dict],
    tags: list[dict],
    signatures: dict[str, dict],
    graph: str = GRAPH,
) -> None:
    apply_schema(client, graph)

    def q(cypher: str, params: dict | None = None):
        return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    # connected_by marks this as a public record, not an owner connection (§4.5 rule 4).
    q(
        "MERGE (o:Org {id: $id}) "
        "SET o.name = $id, o.pack = 'oss', o.connected_by = 'public_record'",
        {"id": ORG_ID},
    )

    seen = first_seen_map(commits, tags)

    commit_rows = [
        {
            "hid": c["hid"],
            "first_seen": seen[c["hid"]],
            "sha": c["sha"],
            "at": c["at"],
            "files": c["files_touched"],
            "release_target": c["release_target"],
        }
        for c in commits
    ]
    for batch in _chunks(commit_rows):
        q(
            """UNWIND $rows AS r
               MERGE (a:Actor {hid: r.hid})
                 SET a.kind = 'human', a.first_seen_in_org = r.first_seen
               MERGE (c:Action {ref: r.sha})
                 SET c.kind = 'commit', c.at = r.at, c.files_touched = r.files,
                     c.release_target = r.release_target
               MERGE (a)-[d:DID]->(c)
                 SET d.at = r.at""",
            {"rows": batch},
        )

    # handle_public only for the already-public persona (§4.5 rule 7).
    personas = sorted({(c["hid"], c["handle_public"]) for c in commits if "handle_public" in c})
    q(
        "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}) SET a.handle_public = r.handle",
        {"rows": [{"hid": hid, "handle": handle} for hid, handle in personas]},
    )

    release_rows = []
    for t in tags:
        if t["kind"] != "annotated":
            continue
        sig = signatures[t["name"]]
        release_rows.append(
            {
                "name": t["name"],
                "target": t["target_sha"],
                "at": t["at"],
                "hid": t["tagger_hid"],
                "first_seen": seen.get(t["tagger_hid"]) if t["tagger_hid"] else None,
                "sig": sig["state"],
                "verified": sig["verified"],
            }
        )
    for batch in _chunks([r for r in release_rows if r["hid"]]):
        q(
            """UNWIND $rows AS r
               MERGE (a:Actor {hid: r.hid})
                 SET a.kind = 'human', a.first_seen_in_org = r.first_seen
               MERGE (rel:Action {ref: r.name})
                 SET rel.kind = 'release', rel.at = r.at, rel.target_ref = r.target,
                     rel.signature_state = r.sig
               MERGE (p:Path {channel: 'git', verified: r.verified})
               MERGE (rel)-[:VIA]->(p)
               MERGE (a)-[d:DID]->(rel)
                 SET d.at = r.at""",
            {"rows": batch},
        )
    # An annotated tag always has a tagger in practice. If one did not, it still gets its
    # release action and path, just no DID edge.
    for batch in _chunks([r for r in release_rows if not r["hid"]]):
        q(
            """UNWIND $rows AS r
               MERGE (rel:Action {ref: r.name})
                 SET rel.kind = 'release', rel.at = r.at, rel.target_ref = r.target,
                     rel.signature_state = r.sig
               MERGE (p:Path {channel: 'git', verified: r.verified})
               MERGE (rel)-[:VIA]->(p)""",
            {"rows": batch},
        )


def graph_counts(client: FalkorClient, graph: str = GRAPH) -> dict[str, dict[str, int]]:
    """Node counts by label and edge counts by type."""
    nodes = client.query(
        graph, "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS c ORDER BY label"
    ).result_set
    edges = client.query(
        graph, "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY t"
    ).result_set
    return {"nodes": dict(nodes), "edges": dict(edges)}


def scan_for_at_sign(client: FalkorClient, graph: str = GRAPH) -> list[str]:
    """Where an '@' appears in any node or edge property. Returns locations, never values."""
    hits: list[str] = []
    for kind, cypher in (("node", "MATCH (n) RETURN n"), ("edge", "MATCH ()-[r]->() RETURN r")):
        for (entity,) in client.query(graph, cypher, timeout_ms=WRITE_TIMEOUT_MS).result_set:
            label = getattr(entity, "labels", None) or [getattr(entity, "relation", "?")]
            for key, value in entity.properties.items():
                if "@" in key or "@" in str(value):
                    hits.append(f"{kind}:{label[0]}.{key}")
    return sorted(set(hits))
