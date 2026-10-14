"""pack-oss tool logic (spec §12.1): four read-only questions for the open-source pack.

  release_path(org, version)          the path one release took, against the project's normal
  grant_history(org)                  who was granted which privilege, and when (hashed ids)
  ecosystem_overlap(ecosystem)        how many identities show up in more than one place
  upstream_context(package, version)  release path + takeover cost + guardians for a dependency
                                      upgrade, in one answer (the `package` is the org id)

Every read goes through the read-only guard with an explicit timeout and a LIMIT; org reads filter
on as-of T. Nothing here writes or calls an LLM. A thing that cannot be computed says
NOT COMPUTED and why. The MCP server (server.py) only registers these functions.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from core.detectors.bypass import bypass
from core.graph.as_of import run_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import ro_query
from core.takeover import scratch as sc

_core_path = Path(__file__).resolve().parents[1] / "hearthguard-core" / "tools.py"
_spec = importlib.util.spec_from_file_location("hearthguard_core_tools", _core_path)
core_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core_tools)

RELEASE_QUERY = (
    "MATCH (a:Action {kind: 'release', ref: $version}) WHERE a.at <= $T "
    "OPTIONAL MATCH (a)-[:VIA]->(p:Path) "
    "RETURN a.ref AS ref, a.at AS at, p.channel AS channel, p.callback AS callback, "
    "p.approvers AS approvers ORDER BY a.at DESC, a.ref LIMIT 1"
)
GRANTS_QUERY = (
    "MATCH (a:Actor)-[g:GRANTED]->(p:Privilege) WHERE g.at <= $T "
    "RETURN a.hid AS hid, p.kind AS privilege, g.at AS at ORDER BY at, hid, privilege LIMIT 1000"
)
OVERLAP_QUERY = (
    "MATCH (i:Identity)-[:EMITTED]->(:Signal)-[:RECORDED_IN]->(p:Place) "
    "WITH i, collect(DISTINCT p.ref) AS places "
    "RETURN size(places) AS n_places, count(i) AS identities ORDER BY n_places LIMIT 100"
)
PLACES_QUERY = "MATCH (p:Place) RETURN p.ref AS ref, p.kind AS kind ORDER BY ref LIMIT 100"
IDENTITIES_QUERY = "MATCH (i:Identity) RETURN count(i) AS n LIMIT 1"


def release_path(client: FalkorClient, org: str, version: str, T: int | None = None) -> dict:
    t, defaulted = core_tools.as_of_time(client, org, T)
    rows = run_as_of(
        client, sc.graph_for(org), RELEASE_QUERY, {"version": version, "T": t}
    ).result_set
    out: dict = {"org": org, "version": version, "T": t, "T_defaulted": defaulted}
    if not rows:
        out.update(found=False, reason="no release with this ref at or before T")
        return out
    ref, at, channel, callback, approvers = rows[0]
    out.update(
        found=True, at=at, path={"channel": channel, "callback": callback, "approvers": approvers}
    )
    if channel is None:
        out["versus_normal"] = {"status": "NOT_COMPUTED", "reason": "the release records no path"}
        return out
    v = bypass(client, org, ref, t)
    out["versus_normal"] = {
        "status": v.status,
        "reason": v.reason,
        "properties": v.evidence.get("properties"),
    }
    return out


def grant_history(client: FalkorClient, org: str, T: int | None = None) -> dict:
    t, defaulted = core_tools.as_of_time(client, org, T)
    rows = run_as_of(client, sc.graph_for(org), GRANTS_QUERY, {"T": t}).result_set
    return {
        "org": org,
        "T": t,
        "T_defaulted": defaulted,
        "grants": [{"actor_hid": h, "privilege": p, "at": at} for h, p, at in rows],
        "complete": False if not rows else None,
        "note": "git records no grants; an empty list means none are documented, not that none "
        "happened (eval/results/xz_grants_unknown.json)"
        if not rows
        else "grants documented by MAINTAINERS / CODEOWNERS / collaborator records only",
    }


def ecosystem_overlap(client: FalkorClient, ecosystem: str) -> dict:
    graph = f"ecosystem_{ecosystem}"
    if graph not in {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }:
        return {"ecosystem": ecosystem, "found": False, "reason": f"no graph {graph}"}

    def q(cypher):
        return ro_query(client, graph, cypher, {}, timeout_ms=DEFAULT_TIMEOUT_MS).result_set

    by_places = {int(n): int(c) for n, c in q(OVERLAP_QUERY)}
    return {
        "ecosystem": ecosystem,
        "found": True,
        "identities": int(q(IDENTITIES_QUERY)[0][0]),
        "places": [{"ref": r, "kind": k} for r, k in q(PLACES_QUERY)],
        "identities_by_number_of_places": by_places,
        "in_more_than_one_place": sum(c for n, c in by_places.items() if n >= 2),
        "note": "hashed identities, counts only; no name is returned",
    }


def upstream_context(
    client: FalkorClient, package: str, version: str, privilege: str = "release"
) -> dict:
    """What to know before accepting a dependency upgrade: how the release was made, how many
    people could take the package over, and how many are on every route."""
    org = package
    rp = release_path(client, org, version)
    return {
        "package": package,
        "version": version,
        "release_path": rp,
        "takeover_cost": core_tools.takeover_cost(client, org, privilege, rp["T"]),
        "guardians": core_tools.guardians_(client, org, privilege, rp["T"]),
        "note": "evidence for a human, not a verdict; each part says NOT COMPUTED when it "
        "could not run",
    }
