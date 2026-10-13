"""Plant a scaffold and red-team campaigns into a COPY of an org graph (spec section 6.3).

Never call this on a real graph (org_tallowdate, org_xz). The runner copies first; assert_copy()
refuses a graph whose name is one of the real org graphs.

Two things are planted, both synthetic and both flagged synthetic: true, planted: true and a
campaign_id (the scaffold has its own id):

  scaffold   The benign structure the campaigns attack. Neither public graph records a grant or a
             release path (git has no grant record), so there is nothing for Rush, Bypass, takeover
             cost or guardians to read. The scaffold adds, for each privilege: one keeper with a
             CAN_GRANT edge (approvals_required 1), six past grantees (GRANTED, with the historical
             days-to-grant in redteam.generate.BASELINE_GRANT_DAYS), and a release history on the
             normal path (CI, provenance) at a fixed cadence that continues through the campaign
             horizon. It also adds one Normal(usual_path) node. These are generator parameters, not
             facts about any project.
  campaign   One campaign's actors, actions, claims, SHARES edges, grant and release.

Every write is MERGE on a unique key (Actor.hid, Action.ref, Claim.id, Place/Path.ref), so planting
twice changes nothing. Identifiers are HMAC hashes (core/graph/hashing.py); the salt is read from
.env and is never written anywhere.

Times: E0 = the day after (latest Action.at in the base graph + EPOCH_BUFFER_DAYS); day 0 of every
campaign is E0 + CAMPAIGN_START_DAYS. The buffer keeps the real graph's last 90 days of commits
out of the active-keepers window of the planted epoch.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.graph.client import FalkorClient
from core.graph.hashing import identifier_hash
from core.graph.schema import apply_schema
from redteam import generate as gen

DAY_S = 86_400
WRITE_TIMEOUT_MS = 60_000
EPOCH_BUFFER_DAYS = 91
CAMPAIGN_START_DAYS = 30
HISTORY_DAYS_BEFORE_E0 = 1095
HORIZON_DAYS_AFTER_E0 = 1100
REAL_GRAPHS = frozenset({"org_tallowdate", "org_xz"})

LABEL = "campaign planted into a copy of public history; not a finding about the project"


class NotACopyError(ValueError):
    """Planting was about to touch a real org graph."""


def assert_copy(graph: str) -> None:
    if graph in REAL_GRAPHS or not (graph.startswith(("redteam_", "harden_", "org_rt", "org_hz"))):
        raise NotACopyError(f"{graph!r} is not a red-team or hardening copy; refusing to plant")


def hid(owner: str, role: str) -> str:
    return identifier_hash(f"{owner}|{role}")


def epoch(client: FalkorClient, graph: str) -> int:
    """E0, the first second of the planted epoch, from the latest Action.at in `graph`."""
    r = client.graph(graph).ro_query("MATCH (a:Action) RETURN max(a.at) LIMIT 1", timeout=10_000)
    last = r.result_set[0][0]
    if last is None:
        raise ValueError(f"{graph} has no Action to anchor the epoch on")
    return (int(last) // DAY_S + EPOCH_BUFFER_DAYS + 1) * DAY_S


def day0(e0: int) -> int:
    return e0 + CAMPAIGN_START_DAYS * DAY_S


def at(day0_ts: int, day: float) -> int:
    return day0_ts + round(day * DAY_S)


def _q(client: FalkorClient, graph: str, cypher: str, params: dict):
    return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)


FLAGS = "synthetic: true, planted: true, campaign_id: $cid"

Q_ACTORS = """UNWIND $rows AS r
MERGE (a:Actor {hid: r.hid})
  SET a.kind = 'human', a.first_seen_in_org = r.first_seen, a.synthetic = true,
      a.planted = true, a.campaign_id = $cid"""
Q_ACTIONS = """UNWIND $rows AS r
MERGE (a:Actor {hid: r.hid})
MERGE (c:Action {ref: r.ref})
  SET c.kind = r.kind, c.at = r.at, c.synthetic = true, c.planted = true, c.campaign_id = $cid
MERGE (a)-[d:DID]->(c)
  SET d.at = r.at, d.synthetic = true, d.planted = true, d.campaign_id = $cid"""
Q_PATHS = """UNWIND $rows AS r
MATCH (c:Action {ref: r.ref})
MERGE (p:Path {ref: r.ref})
  SET p.channel = r.path.channel, p.verified = r.path.verified, p.ci = r.path.ci,
      p.provenance = r.path.provenance, p.key_hid = r.path.key_hid,
      p.publisher_in_set = r.path.publisher_in_set,
      p.artifact_matches_tag = r.path.artifact_matches_tag,
      p.synthetic = true, p.planted = true, p.campaign_id = $cid
MERGE (c)-[v:VIA]->(p)
  SET v.synthetic = true, v.planted = true, v.campaign_id = $cid"""
Q_PRIVS = """UNWIND $kinds AS k
MERGE (p:Privilege {kind: k})
  SET p.sensitive = true, p.synthetic = true, p.planted = true, p.campaign_id = $cid"""
Q_CAN_GRANT = """UNWIND $rows AS r
MATCH (a:Actor {hid: r.hid}), (p:Privilege {kind: r.priv})
MERGE (a)-[e:CAN_GRANT]->(p)
  SET e.approvals_required = 1, e.synthetic = true, e.planted = true, e.campaign_id = $cid"""
Q_GRANTED = """UNWIND $rows AS r
MATCH (a:Actor {hid: r.hid}), (p:Privilege {kind: r.priv})
MERGE (a)-[e:GRANTED]->(p)
  SET e.at = r.at, e.by_hid = r.by_hid, e.evidence_ref = r.ref,
      e.synthetic = true, e.planted = true, e.campaign_id = $cid"""
Q_CLAIMS = """UNWIND $rows AS r
MATCH (a:Actor {hid: r.hid})
MERGE (c:Claim {id: r.id})
  SET c.kind = r.kind, c.at = r.at, c.confidence = 0.9, c.modality = 'stated',
      c.target_hid = r.target, c.synthetic = true, c.planted = true, c.campaign_id = $cid
MERGE (a)-[s:ASSERTED]->(c)
  SET s.synthetic = true, s.planted = true, s.campaign_id = $cid"""
Q_SHARES = """UNWIND $rows AS r
MATCH (a:Actor {hid: r.a}), (b:Actor {hid: r.b})
MERGE (a)-[s:SHARES {signal: r.signal}]->(b)
  SET s.strength = 1.0, s.synthetic = true, s.planted = true, s.campaign_id = $cid"""
Q_NORMAL = """MERGE (o:Org)
MERGE (n:Normal {metric: 'usual_path', scope: 'release', window: '730d', computed_at: $e0})
  SET n.value = 'ci', n.synthetic = true, n.planted = true, n.campaign_id = $cid
MERGE (n)-[r:OF]->(o)
  SET r.synthetic = true, r.planted = true, r.campaign_id = $cid"""


@dataclass
class Scaffold:
    id: str
    e0: int
    keepers: int
    privileges: tuple[str, ...]
    keeper_hids: list[str]
    n_history_grants: int
    n_releases: int


def plant_scaffold(
    client: FalkorClient,
    graph: str,
    scaffold_id: str,
    e0: int,
    *,
    keepers: int = 1,
    privileges: tuple[str, ...] = gen.PRIVILEGES,
) -> Scaffold:
    """Plant the benign structure into `graph` (a copy). Idempotent."""
    assert_copy(graph)
    apply_schema(client, graph)
    p = {"cid": scaffold_id}
    keeper_hids = [hid(scaffold_id, f"keeper-{k}") for k in range(keepers)]
    actors: list[dict] = [{"hid": h, "first_seen": e0 - 3000 * DAY_S} for h in keeper_hids]
    actions: list[dict] = []
    grants: list[dict] = []
    for priv in privileges:
        for i, days in enumerate(gen.BASELINE_GRANT_DAYS):
            who = hid(scaffold_id, f"past-{priv}-{i}")
            grant_at = e0 - (1500 - 150 * i) * DAY_S
            first_at = grant_at - days * DAY_S
            actors.append({"hid": who, "first_seen": first_at})
            actions.append(
                {
                    "hid": who,
                    "ref": f"{scaffold_id}:{priv}:{i}:first",
                    "kind": "contribution",
                    "at": first_at,
                }
            )
            grants.append(
                {
                    "hid": who,
                    "priv": priv,
                    "at": grant_at,
                    "by_hid": keeper_hids[0],
                    "ref": f"{scaffold_id}:{priv}:{i}:grant",
                }
            )
    releases: list[dict] = []
    k = 0
    t = e0 - HISTORY_DAYS_BEFORE_E0 * DAY_S
    end = e0 + HORIZON_DAYS_AFTER_E0 * DAY_S
    while t <= end:
        ref = f"{scaffold_id}:release:{k}"
        actions.append({"hid": keeper_hids[0], "ref": ref, "kind": "release", "at": t})
        releases.append({"ref": ref, "path": dict(gen.NORMAL_PATH)})
        k += 1
        t += gen.RELEASE_CADENCE_DAYS * DAY_S
    _q(client, graph, Q_ACTORS, {**p, "rows": actors})
    _q(client, graph, Q_ACTIONS, {**p, "rows": actions})
    _q(client, graph, Q_PATHS, {**p, "rows": releases})
    _q(client, graph, Q_PRIVS, {**p, "kinds": list(privileges)})
    _q(
        client,
        graph,
        Q_CAN_GRANT,
        {**p, "rows": [{"hid": h, "priv": pr} for h in keeper_hids for pr in privileges]},
    )
    _q(client, graph, Q_GRANTED, {**p, "rows": grants})
    _q(client, graph, Q_NORMAL, {**p, "e0": e0})
    return Scaffold(
        scaffold_id, e0, keepers, tuple(privileges), keeper_hids, len(grants), len(releases)
    )


def plant_campaign(client: FalkorClient, graph: str, camp: gen.Campaign, day0_ts: int) -> dict:
    """Plant one campaign into `graph` (a copy). Returns the resolved events for the scorer:
    absolute times, the attacker's hid and the privilege. Idempotent."""
    assert_copy(graph)
    cid = camp.id
    p = {"cid": cid}
    subject_role = "newcomer" if camp.clean else "attacker"
    subject = hid(cid, subject_role)
    roles = sorted({e.actor for e in camp.events})
    hids = {r: hid(cid, r) for r in roles}

    first_seen: dict[str, int] = {}
    for e in camp.events:
        t = at(day0_ts, e.day)
        first_seen[e.actor] = min(t, first_seen.get(e.actor, t))
    actors = [{"hid": hids[r], "first_seen": first_seen[r]} for r in roles]

    actions, paths, grants, claims = [], [], [], []
    resolved = []
    for i, e in enumerate(camp.events):
        t = at(day0_ts, e.day)
        ref = f"{cid}:{i:03d}"
        row = {"i": i, "day": e.day, "at": t, "actor": e.actor, "kind": e.kind, "move": e.move}
        if e.kind in ("contribution", "account_created", "release"):
            actions.append({"hid": hids[e.actor], "ref": ref, "kind": e.kind, "at": t})
            row["ref"] = ref
        if e.kind == "release":
            paths.append({"ref": ref, "path": e.path})
        if e.kind == "grant":
            grants.append(
                {"hid": hids[e.actor], "priv": e.privilege, "at": t, "by_hid": None, "ref": ref}
            )
        if e.kind == "claim":
            claims.append(
                {
                    "hid": hids[e.actor],
                    "id": ref,
                    "kind": e.claim_kind,
                    "at": t,
                    "target": subject if e.claim_kind == "VOUCH" else None,
                }
            )
        resolved.append(row)
    shares = []
    socks = [r for r in roles if r.startswith("sock-")]
    for a in range(len(socks)):
        for b in range(a + 1, len(socks)):
            for sig in camp.sock_signals:
                shares.append({"a": hids[socks[a]], "b": hids[socks[b]], "signal": sig})

    _q(client, graph, Q_ACTORS, {**p, "rows": actors})
    if actions:
        _q(client, graph, Q_ACTIONS, {**p, "rows": actions})
    if paths:
        _q(client, graph, Q_PATHS, {**p, "rows": paths})
    if grants:
        _q(client, graph, Q_GRANTED, {**p, "rows": grants})
    if claims:
        _q(client, graph, Q_CLAIMS, {**p, "rows": claims})
    if shares:
        _q(client, graph, Q_SHARES, {**p, "rows": shares})
    return {
        "campaign_id": cid,
        "subject_hid": subject,
        "events": resolved,
        "privilege": camp.privilege,
    }


def strip_flags(client: FalkorClient, graph: str) -> None:
    """Remove synthetic, planted and campaign_id from every node and edge of a COPY. Only the
    flag-independence test calls this: detectors must give the same answers afterwards."""
    assert_copy(graph)
    for stmt in (
        "MATCH (n) REMOVE n.synthetic, n.planted, n.campaign_id",
        "MATCH ()-[r]->() REMOVE r.synthetic, r.planted, r.campaign_id",
    ):
        client.query(graph, stmt, timeout_ms=WRITE_TIMEOUT_MS)
