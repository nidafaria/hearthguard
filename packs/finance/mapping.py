"""Finance pack mapping (spec §4.2 thing 2, §6.1): parsed records -> the org graph's core concepts.

  email, chat, portal event   -> Action (DID by its author, RECORDED_IN its Place)
  ERP bank-detail change      -> Action{kind:'bank_change'} VIA Path {channel, callback, approvers}
  ERP grant                   -> (:Actor)-[:GRANTED {at, by_hid, evidence_ref}]->(:Privilege)
  ERP policy + HR leave       -> (:Actor)-[:CAN_GRANT {approvals_required, at}]->(:Privilege)
  inbox, chat channel, portal, ERP log -> Place;  everyone on a message, chat or portal event
                                          -> PARTICIPATES_IN {since, last_at}

The graph is loaded as of a horizon `as_of`: records dated after it are not read. The pack decides
one thing the core cannot express, who can approve at the horizon, because edges in the core only
ever appear and never end:
  - A holder named in the ERP policy for a privilege can approve unless an ERP leave record started
    at or before `as_of` and ends after it. A holder on leave at the horizon gets no CAN_GRANT edge.
  - approvals_required = min(policy approvers, holders available at the horizon). So when the
    policy asks for two approvers and one holder is away, one approval is all that is left to win.
That is a derived value, written down here and recomputed for each horizon. Load the same data at
two horizons to compare before and after a leave.

Writes are MERGE on unique keys (Actor.hid, Action.ref, Place.ref, Privilege.kind, Path.ref), so a
second load changes no count. Every node carries `synthetic: true`. A planted record's Action and
Actor carry `planted: true` and `campaign_id`; detectors never read these flags (CLAUDE.md).
"""

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from core.memory import who_saw
from packs.finance import pack

WRITE_TIMEOUT_MS = 60_000
ORG_ID = "northbridge"


def _q(client: FalkorClient, graph: str, cypher: str, params: dict | None = None):
    return client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)


def available_holders(policy: dict, leaves: list[dict], as_of: int) -> list[str]:
    """Holders of a policy's privilege not on leave at `as_of` (leave.at <= as_of < until)."""
    away = {lv["hid"] for lv in leaves if lv["at"] <= as_of < lv["until"]}
    return [h for h in policy["holders"] if h not in away]


def can_grant_rows(parsed: list[dict], as_of: int) -> list[dict]:
    """CAN_GRANT rows at the horizon. The latest policy per privilege at or before it wins."""
    leaves = [p for p in parsed if p.get("entry") == "leave" and p["at"] <= as_of]
    latest: dict[str, dict] = {}
    for p in parsed:
        if p.get("entry") == "policy" and p["at"] <= as_of:
            if p["privilege"] not in latest or p["at"] >= latest[p["privilege"]]["at"]:
                latest[p["privilege"]] = p
    rows = []
    for priv, policy in sorted(latest.items()):
        here = available_holders(policy, leaves, as_of)
        for h in here:
            rows.append(
                {
                    "hid": h,
                    "privilege": priv,
                    "at": policy["at"],
                    "approvals_required": min(policy["approvers_required"], len(here)),
                }
            )
    return rows


def _actor_rows(visible: list[dict]) -> list[dict]:
    """One row per actor: the earliest time it appears, acting, on a message, or as a holder."""
    first: dict[str, int] = {}
    for e in visible:
        people = [e["hid"], *e.get("seen_by", [])] if "hid" in e else []
        if e.get("entry") == "grant":
            people.append(e["by_hid"])
        if e.get("entry") == "policy":
            people += e["holders"]
        for who in people:
            first[who] = min(e["at"], first.get(who, e["at"]))
    return [{"hid": h, "first": t} for h, t in sorted(first.items())]


def load(
    client: FalkorClient,
    graph: str,
    parsed: list[dict],
    as_of: int,
    org_id: str = ORG_ID,
) -> dict:
    """Load `parsed` records dated at or before `as_of` into `graph`. Returns what was loaded."""
    visible = [p for p in parsed if p["at"] <= as_of]
    apply_schema(client, graph)
    _q(
        client,
        graph,
        "MERGE (o:Org {id: $id}) SET o.name = $id, o.pack = 'finance', "
        "o.connected_by = 'synthetic', o.synthetic = true",
        {"id": org_id},
    )
    _q(
        client,
        graph,
        "UNWIND $rows AS r MERGE (p:Privilege {kind: r.kind}) SET p.sensitive = r.sensitive, "
        "p.synthetic = true",
        {"rows": [{"kind": p.kind, "sensitive": p.sensitive} for p in pack.PRIVILEGES]},
    )

    # Actors. An actor is planted only if every event it acted in is planted (and it acted).
    actors = _actor_rows(visible)
    planted_actor = {}
    for e in visible:
        if "hid" in e:
            planted_actor.setdefault(e["hid"], []).append(e["planted"])
    _q(
        client,
        graph,
        "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) "
        "SET a.kind = 'human', a.first_seen_in_org = r.first, a.synthetic = true, "
        "a.planted = r.planted, a.campaign_id = r.campaign",
        {
            "rows": [
                {
                    "hid": a["hid"],
                    "first": a["first"],
                    "planted": bool(planted_actor.get(a["hid"])) and all(planted_actor[a["hid"]]),
                    "campaign": next(
                        (e["campaign_id"] for e in visible if e.get("hid") == a["hid"]
                         and e["planted"]),
                        None,
                    ),
                }
                for a in actors
            ]
        },
    )  # fmt: skip

    # Places, then Actions (message, chat, portal event) with DID and RECORDED_IN.
    places = {e["place"]["ref"]: e["place"] for e in visible if "place" in e}
    who_saw.write_places(client, graph, sorted(places.values(), key=lambda p: p["ref"]))
    acts = [e for e in visible if e.get("kind") in ("email", "chat", "portal_event")]
    _q(
        client,
        graph,
        "UNWIND $rows AS r MERGE (x:Action {ref: r.ref}) "
        "SET x.kind = r.kind, x.at = r.at, x.vendor = r.vendor, x.synthetic = true, "
        "x.planted = r.planted, x.campaign_id = r.campaign "
        "WITH x, r MATCH (a:Actor {hid: r.hid}) MERGE (a)-[d:DID]->(x) SET d.at = r.at",
        {"rows": [_action_row(e) for e in acts]},
    )

    # Bank-detail changes: Action, Path, DID, APPROVED.
    bcs = [e for e in visible if e.get("entry") == "bank_change"]
    _q(
        client,
        graph,
        "UNWIND $rows AS r MERGE (x:Action {ref: r.ref}) "
        "SET x.kind = 'bank_change', x.at = r.at, x.vendor = r.vendor, x.synthetic = true, "
        "x.planted = r.planted, x.campaign_id = r.campaign "
        "MERGE (p:Path {ref: r.ref}) "
        "SET p.channel = r.channel, p.callback = r.callback, p.verified = r.callback, "
        "p.approvers = r.approvers, p.synthetic = true "
        "MERGE (x)-[:VIA]->(p) "
        "WITH x, r MATCH (a:Actor {hid: r.hid}) MERGE (a)-[d:DID]->(x) SET d.at = r.at",
        {"rows": [{**_action_row(e), **_path_fields(e)} for e in bcs]},
    )
    approvals = [{"ref": e["ref"], "hid": h, "at": e["at"]} for e in bcs for h in e["approved_by"]]
    _q(
        client,
        graph,
        "UNWIND $rows AS r MATCH (x:Action {ref: r.ref}) MATCH (a:Actor {hid: r.hid}) "
        "MERGE (a)-[p:APPROVED]->(x) SET p.at = r.at",
        {"rows": approvals},
    )

    # Grants, then the approval authority at the horizon.
    grants = [e for e in visible if e.get("entry") == "grant"]
    _q(
        client,
        graph,
        "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}) MATCH (p:Privilege {kind: r.kind}) "
        "MERGE (a)-[g:GRANTED]->(p) SET g.at = r.at, g.by_hid = r.by, g.evidence_ref = r.ref",
        {
            "rows": [
                {"hid": g["hid"], "kind": g["privilege"], "at": g["at"], "by": g["by_hid"],
                 "ref": g["ref"]}
                for g in grants
            ]
        },
    )  # fmt: skip
    cg = can_grant_rows(parsed, as_of)
    _q(
        client,
        graph,
        "UNWIND $rows AS r MATCH (a:Actor {hid: r.hid}) MATCH (p:Privilege {kind: r.privilege}) "
        "MERGE (a)-[e:CAN_GRANT]->(p) SET e.approvals_required = r.approvals_required, e.at = r.at",
        {"rows": cg},
    )

    # Visibility: who participates where and since when, and what was recorded where.
    events = []
    for e in visible:
        if e.get("kind") in ("email", "chat", "portal_event"):
            for who in [e["hid"], *e.get("seen_by", [])]:
                events.append({"hid": who, "place": e["place"]["ref"], "at": e["at"]})
    rows = who_saw.participation_rows(events)
    who_saw.write_participation(client, graph, rows)
    recorded = [{"ref": e["ref"], "place": e["place"]["ref"]} for e in acts + bcs]
    who_saw.write_recorded_in(client, graph, recorded)

    return {
        "records_visible": len(visible),
        "actors": len(actors),
        "actions": len(acts) + len(bcs),
        "grants": len(grants),
        "can_grant": len(cg),
        "participates_in": len(rows),
        "recorded_in": len(recorded),
    }


def _action_row(e: dict) -> dict:
    return {
        "ref": e["ref"],
        "kind": e["kind"],
        "at": e["at"],
        "vendor": e["vendor"],
        "hid": e["hid"],
        "planted": e["planted"],
        "campaign": e["campaign_id"],
    }


def _path_fields(e: dict) -> dict:
    return {"channel": e["channel"], "callback": e["callback"], "approvers": e["approvers"]}
