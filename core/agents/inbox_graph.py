"""Inbox nodes in the org graph (docs/HEARTHGUARD.md 6.1): Finding, Gap, Note, Draft,
OwnerDecision, Task, AgentStep, Hardening, and the Org BACKUP edge.

Every write is MERGE on a unique key, so a repeat or a double tap changes nothing. Every query has
an explicit timeout. Evidence is read as of the quarter-end T. Nothing here reads the
`synthetic`, `planted` or `campaign_id` flags (CLAUDE.md, detectors must never read them).

Objection and Request: add_objection()/add_request() write them. No Skeptic exists in this repo
yet, so sync_case() has no source for them and writes none (eval/results/blockers_a.md, row 38).
"""

import functools
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import yaml

from core.agents.cases import MOVES, Case, epoch
from core.graph import schema
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient

WRITE_MS = 20_000
READ_MS = 10_000
DAY_S = 86_400
FROZEN = Path(__file__).resolve().parents[2] / "config" / "frozen.yaml"
EVIDENCE_KINDS = ["PRESSURE", "URGENCY", "VOUCH", "CAPACITY_STATEMENT"]

# (label, property) that need a unique key beyond the 6.6 list, for idempotent MERGE.
EXTRA_UNIQUE = (
    ("OwnerDecision", "key"),
    ("Draft", "key"),
    ("Gap", "key"),
    ("Hardening", "key"),
    ("AgentStep", "id"),
    ("Objection", "id"),
    ("Request", "id"),
)

Clock = Callable[[], int]


def short(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def ensure_schema(client: FalkorClient, graph: str) -> None:
    schema.apply_schema(client, graph)
    present = schema.range_indexes(client, graph)
    for label, prop in EXTRA_UNIQUE:
        schema._range_node_index(client, graph, label, prop, present)
        schema._unique_constraint(client, graph, label, prop)


def finding_id(case: Case, quarter: str) -> str:
    return f"{case.id}:{quarter}"


def note_id(case: Case, quarter: str) -> str:
    return f"note:{case.id}:{quarter}"


def pressure_window_days() -> int:
    return int(yaml.safe_load(FROZEN.read_text(encoding="utf-8"))["pressure"]["window_days"])


def status_cells(case: Case, results: Path, quarter: str) -> dict[str, dict]:
    """takeover_cost and guardians cells for one quarter, from the saved status files."""
    cells: dict[str, dict] = {}
    for name in case.detail_files:
        path = results / name
        if not path.exists():
            continue
        for q in json.loads(path.read_text(encoding="utf-8"))["quarters"]:
            if q["quarter"] == quarter:
                for key in ("takeover_cost", "guardians"):
                    if key in q.get("checks", {}):
                        cells.setdefault(key, q["checks"][key])
    return cells


def _moves_list(row: dict) -> list[str]:
    items = [f"{m}={row['moves'][m]}" for m in MOVES]
    items.append(f"LONE_KEEPER={row['lone_keeper']}")
    return items


def sync_case(
    client: FalkorClient, case: Case, rows: list[dict], results: Path, now: Clock
) -> dict:
    """Write one Finding and one Note per quarter, link their evidence, and write Gap nodes.

    Returns counts of what exists afterwards. Safe to run any number of times.
    """
    graph = case.graph
    ensure_schema(client, graph)
    window = pressure_window_days()
    for row in rows:
        cells = status_cells(case, results, row["quarter"])
        tc, gd = cells.get("takeover_cost", {}), cells.get("guardians", {})
        fid = finding_id(case, row["quarter"])
        status = "held" if row["decision"] == "HOLD" else "open"
        client.query(
            graph,
            """MERGE (o:Org {id: $org})
               MERGE (f:Finding {id: $fid})
               SET f.quarter = $q, f.case = $case, f.moves = $moves, f.decision = $decision,
                   f.at = $T, f.score = $score, f.takeover_cost = $tcv,
                   f.takeover_cost_status = $tcs, f.guardians = $gv, f.guardians_status = $gs
               SET f.status = CASE WHEN f.status = 'dismissed' THEN 'dismissed' ELSE $status END
               MERGE (n:Note {id: $nid})
                 ON CREATE SET n.created_at = $now, n.routed_to_hid = 'owner',
                               n.sent_to_slack = false
               SET n.quarter = $q, n.case = $case
               MERGE (n)-[:FOR]->(f)""",
            {
                "org": case.org,
                "fid": fid,
                "nid": note_id(case, row["quarter"]),
                "q": row["quarter"],
                "case": case.id,
                "moves": _moves_list(row),
                "decision": row["decision"],
                "T": row["T"],
                "score": row["detail"].get("breakdown", {}).get("risk_x_moves"),
                "tcv": tc.get("value"),
                "tcs": (tc.get("status") or "NOT COMPUTED"),
                "gv": gd.get("value"),
                "gs": (gd.get("status") or "NOT COMPUTED"),
                "status": status,
                "now": now(),
            },
            timeout_ms=WRITE_MS,
        )
        _link_claims(client, graph, fid, row["T"], window)
        _link_normals(client, graph, fid, row["T"])
    gaps = _write_gaps(client, case, rows, results)
    remembered = _apply_owner_memory(client, case, rows)
    return {"findings": len(rows), "gaps": gaps, "remembered": remembered}


# ---- Owner memory: a dismissed situation does not return without new evidence (spec 9) ----------


def situation_of(decision: str, moves: list[str]) -> str:
    """The whole situation: the decision and every move's status, lone keeper included. The same
    string is built from a Finding node (f.decision, f.moves) and from a saved row."""
    return "|".join([decision, *sorted(moves)])


def _apply_owner_memory(client: FalkorClient, case: Case, rows: list[dict]) -> int:
    """Hold a Finding back when its situation matches an earlier owner dismissal and no evidence
    has arrived since. New evidence (a Claim later than the dismissal, as of T) reopens it.
    Returns how many findings are held back now."""
    held = 0
    for row in sorted(rows, key=lambda r: r["T"]):
        fid = finding_id(case, row["quarter"])
        sit = situation_of(row["decision"], _moves_list(row))
        prior = client.query(
            case.graph,
            "MATCH (d:OwnerDecision {kind: 'dismiss'})-[:ABOUT]->(g:Finding) "
            "WHERE d.situation = $sit AND g.id <> $fid AND d.at <= $T "
            "RETURN d.key, d.at ORDER BY d.at, d.key LIMIT 1",
            {"sit": sit, "fid": fid, "T": row["T"]},
            timeout_ms=READ_MS,
        )
        if not prior.result_set:
            continue
        dkey, at = prior.result_set[0]
        evidence = run_as_of(
            client,
            case.graph,
            "MATCH (c:Claim) WHERE c.at > $at AND c.at <= $T AND c.kind IN $kinds "
            "RETURN c.id LIMIT 1",
            {"at": at, "T": row["T"], "kinds": EVIDENCE_KINDS},
            timeout_ms=READ_MS,
        )
        new_evidence = bool(evidence.result_set)
        if new_evidence:
            client.query(
                case.graph,
                "MATCH (f:Finding {id: $fid}) WHERE f.remembered = true "
                "SET f.status = 'open', f.remembered = false",
                {"fid": fid},
                timeout_ms=WRITE_MS,
            )
            continue
        client.query(
            case.graph,
            "MATCH (f:Finding {id: $fid}) SET f.status = 'dismissed', f.remembered = true, "
            "f.remembered_by = $dkey "
            "WITH f MATCH (n:Note)-[:FOR]->(f) SET n.remembered_by = $dkey",
            {"fid": fid, "dkey": dkey},
            timeout_ms=WRITE_MS,
        )
        held += 1
    return held


def _link_claims(client: FalkorClient, graph: str, fid: str, T: int, window: int) -> None:
    found = run_as_of(
        client,
        graph,
        "MATCH (c:Claim) WHERE c.at <= $T AND c.at > $start AND c.kind IN $kinds "
        "RETURN c.id ORDER BY c.id LIMIT 1000",
        {"T": T, "start": T - window * DAY_S, "kinds": EVIDENCE_KINDS},
        timeout_ms=READ_MS,
    )
    ids = [r[0] for r in found.result_set]
    if ids:
        client.query(
            graph,
            "UNWIND $ids AS cid MATCH (f:Finding {id: $fid}), (c:Claim {id: cid}) "
            "MERGE (f)-[:SUPPORTED_BY]->(c)",
            {"ids": ids, "fid": fid},
            timeout_ms=WRITE_MS,
        )


def _link_normals(client: FalkorClient, graph: str, fid: str, T: int) -> None:
    """The latest Normal per (metric, window) with computed_at <= T."""
    found = run_as_of(
        client,
        graph,
        "MATCH (n:Normal) WHERE n.computed_at <= $T "
        "RETURN n.metric, n.window, n.computed_at ORDER BY n.metric, n.computed_at LIMIT 1000",
        {"T": T},
        timeout_ms=READ_MS,
    )
    latest: dict[tuple, int] = {}
    for metric, window, at in found.result_set:
        latest[(metric, window)] = at  # rows are ordered by computed_at, so the last one wins
    rows = [{"m": m, "w": w, "at": at} for (m, w), at in latest.items()]
    if rows:
        client.query(
            graph,
            "UNWIND $rows AS r MATCH (f:Finding {id: $fid}), "
            "(n:Normal {metric: r.m, window: r.w, computed_at: r.at}) "
            "MERGE (f)-[:SUPPORTED_BY]->(n)",
            {"rows": rows, "fid": fid},
            timeout_ms=WRITE_MS,
        )


def _write_gaps(client: FalkorClient, case: Case, rows: list[dict], results: Path) -> int:
    """Gap nodes from the saved ecosystem gap query (xz only). Linked to the quarter that
    contains the decision: the earliest quarter-end T at or after the decision time."""
    path = results / "ecosystem_gaps.json"
    if case.id != "xz" or not path.exists():
        return 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    ordered = sorted(rows, key=lambda r: r["T"])
    written = 0
    for d in doc.get("decisions", []):
        if d.get("status") != "COMPUTED":
            continue
        at = epoch(d["decision_at"])
        target = next((r for r in ordered if r["T"] >= at), None)
        if target is None:
            continue
        for g in d.get("gaps", []):
            key = short(f"{d['decision']}|{g['signal']}|{g['gap']}")
            client.query(
                case.graph,
                """MERGE (x:Gap {key: $key})
                   SET x.kind = $kind, x.decision_ref = $dec, x.signal_ref = $sig,
                       x.place_ref = $place, x.at = $at, x.label_confidence = $conf
                   WITH x MATCH (f:Finding {id: $fid}) MERGE (f)-[:SUPPORTED_BY]->(x)""",
                {
                    "key": key,
                    "kind": g["gap"],
                    "dec": d["decision"],
                    "sig": g["signal"],
                    "place": g.get("signal_place"),
                    "at": at,
                    "conf": g.get("label_confidence"),
                    "fid": finding_id(case, target["quarter"]),
                },
                timeout_ms=WRITE_MS,
            )
            written += 1
    return written


# ---- Objection and Request (written by a Skeptic, which does not exist yet) -------------------


def add_objection(client: FalkorClient, graph: str, fid: str, reason: str, now: int) -> str:
    oid = f"objection:{short(fid + '|' + reason)}"
    client.query(
        graph,
        "MATCH (f:Finding {id: $fid}) MERGE (o:Objection {id: $oid}) "
        "SET o.by = 'skeptic', o.reason = $reason, o.open = coalesce(o.open, true), o.at = $now "
        "MERGE (o)-[:ON]->(f)",
        {"fid": fid, "oid": oid, "reason": reason, "now": now},
        timeout_ms=WRITE_MS,
    )
    return oid


def add_request(
    client: FalkorClient, graph: str, oid: str, question: str, frm: str, to: str
) -> str:
    rid = f"request:{short(oid + '|' + question)}"
    client.query(
        graph,
        "MATCH (o:Objection {id: $oid}) MERGE (r:Request {id: $rid}) "
        "SET r.from = $frm, r.to = $to, r.question = $q, r.status = coalesce(r.status, 'open') "
        "MERGE (r)-[:FOR]->(o)",
        {"oid": oid, "rid": rid, "frm": frm, "to": to, "q": question},
        timeout_ms=WRITE_MS,
    )
    return rid


# ---- Note state ---------------------------------------------------------------------------------


def note_state(client: FalkorClient, case: Case, quarter: str) -> dict:
    r = client.query(
        case.graph,
        "MATCH (n:Note {id: $nid})-[:FOR]->(f:Finding) RETURN properties(n), properties(f)",
        {"nid": note_id(case, quarter)},
        timeout_ms=READ_MS,
    )
    if not r.result_set:
        raise KeyError(f"no note for {case.id} {quarter}")
    note, finding = r.result_set[0]
    return {"note": dict(note), "finding": dict(finding)}


def set_route(client: FalkorClient, case: Case, quarter: str, recipients: list[str]) -> None:
    """Record where the note would go: Note.routed_to_hid and the thread's members."""
    client.query(
        case.graph,
        "MATCH (n:Note {id: $nid}) SET n.routed_to_hid = $first, n.thread_hids = $all",
        {"nid": note_id(case, quarter), "first": recipients[0], "all": recipients},
        timeout_ms=WRITE_MS,
    )


def mark(client: FalkorClient, case: Case, quarter: str, prop: str, now: int) -> None:
    """Set Note.opened_at or Note.ack_at the first time only."""
    if prop not in ("opened_at", "ack_at"):
        raise ValueError(prop)
    client.query(
        case.graph,
        f"MATCH (n:Note {{id: $nid}}) SET n.{prop} = coalesce(n.{prop}, $now)",
        {"nid": note_id(case, quarter), "now": now},
        timeout_ms=WRITE_MS,
    )


def agent_step(
    client: FalkorClient,
    case: Case,
    quarter: str,
    *,
    agent: str,
    tool: str,
    reason: str,
    ms: float,
    result_ref: str,
    now: int,
    step_key: str,
) -> None:
    client.query(
        case.graph,
        "MERGE (s:AgentStep {id: $id}) "
        "SET s.agent = $agent, s.tool = $tool, s.reason = $reason, s.ms = $ms, "
        "s.result_ref = $ref, s.llm_calls = 0, s.at = $now, s.note = $nid",
        {
            "id": f"step:{short(note_id(case, quarter) + '|' + tool + '|' + step_key)}",
            "agent": agent,
            "tool": tool,
            "reason": reason,
            "ms": round(ms, 2),
            "ref": result_ref,
            "now": now,
            "nid": note_id(case, quarter),
        },
        timeout_ms=WRITE_MS,
    )


# ---- Owner decision -----------------------------------------------------------------------------


def record_dismissal(client: FalkorClient, case: Case, quarter: str, reason: str, at: int) -> bool:
    """MERGE one OwnerDecision on a unique action key. True only for the call that made it."""
    key = f"dismiss:{case.id}:{quarter}"
    fid = finding_id(case, quarter)
    found = client.query(
        case.graph,
        "MATCH (f:Finding {id: $fid}) RETURN f.decision, f.moves",
        {"fid": fid},
        timeout_ms=READ_MS,
    )
    situation = (
        situation_of(found.result_set[0][0], found.result_set[0][1]) if found.result_set else None
    )
    r = client.query(
        case.graph,
        """MERGE (d:OwnerDecision {key: $key})
             ON CREATE SET d.text = $text, d.at = $at, d.authority = 'owner',
                           d.scope = 'finding', d.kind = 'dismiss', d.situation = $situation
           WITH d
           MATCH (f:Finding {id: $fid}), (n:Note {id: $nid})
           MERGE (d)-[:ABOUT]->(f)
           SET f.status = 'dismissed', n.ack_at = coalesce(n.ack_at, $at)""",
        {
            "key": key,
            "text": reason,
            "at": at,
            "situation": situation,
            "fid": fid,
            "nid": note_id(case, quarter),
        },
        timeout_ms=WRITE_MS,
    )
    return r.nodes_created > 0


def learned_for(client: FalkorClient, case: Case, quarter: str) -> dict | None:
    """What the learning step recorded for this dismissal, or None if it has not run yet."""
    r = client.query(
        case.graph,
        "MATCH (d:OwnerDecision {key: $key}) WHERE d.learning_state IS NOT NULL "
        "RETURN d.exception_id, d.learning_state, d.learning_reason",
        {"key": f"dismiss:{case.id}:{quarter}"},
        timeout_ms=READ_MS,
    )
    if not r.result_set:
        return None
    xid, state, reason = r.result_set[0]
    return {"exception_id": xid, "state": state, "state_reason": reason}


def link_learned(
    client: FalkorClient,
    case: Case,
    quarter: str,
    exception_id: str | None,
    state: str,
    reason: str,
) -> None:
    """Write the learning result on the owner's dismissal. Holds the exception id only, never
    its template: the template lives in the playbook graph."""
    client.query(
        case.graph,
        "MATCH (d:OwnerDecision {key: $key}) SET d.exception_id = $xid, d.learning_state = $state, "
        "d.learning_reason = $reason",
        {
            "key": f"dismiss:{case.id}:{quarter}",
            "xid": exception_id,
            "state": state,
            "reason": reason,
        },
        timeout_ms=WRITE_MS,
    )


def owner_decisions(client: FalkorClient, case: Case, quarter: str) -> list[dict]:
    r = client.query(
        case.graph,
        "MATCH (d:OwnerDecision)-[:ABOUT]->(f:Finding {id: $fid}) "
        "RETURN properties(d) ORDER BY d.at, d.key LIMIT 100",
        {"fid": finding_id(case, quarter)},
        timeout_ms=READ_MS,
    )
    return [dict(row[0]) for row in r.result_set]


# ---- Snooze -------------------------------------------------------------------------------------


def snooze(
    client: FalkorClient, case: Case, quarter: str, until: int, fired: list[str], now: int
) -> bool:
    """Set Note.snoozed_until once. A second tap while snoozed changes nothing. True if set."""
    r = client.query(
        case.graph,
        """MATCH (n:Note {id: $nid})
           WITH n, (n.snoozed_until IS NULL OR n.snoozed_until <= $now) AS fresh
           SET n.snoozed_until = CASE WHEN fresh THEN $until ELSE n.snoozed_until END,
               n.snoozed_moves = CASE WHEN fresh THEN $fired ELSE n.snoozed_moves END,
               n.ack_at = coalesce(n.ack_at, $now)
           RETURN fresh""",
        {"nid": note_id(case, quarter), "until": until, "fired": fired, "now": now},
        timeout_ms=WRITE_MS,
    )
    return bool(r.result_set and r.result_set[0][0])


# ---- Drafts -------------------------------------------------------------------------------------


def create_draft(
    client: FalkorClient, case: Case, quarter: str, kind: str, text: str, now: int
) -> dict:
    """One Draft per (note, kind). A repeat returns the existing one, text untouched."""
    key = f"draft:{note_id(case, quarter)}:{kind}"
    client.query(
        case.graph,
        """MATCH (n:Note {id: $nid})
           MERGE (d:Draft {key: $key})
             ON CREATE SET d.kind = $kind, d.text = $text, d.sent_by_owner = false, d.at = $now
           MERGE (d)-[:FOR]->(n)""",
        {"nid": note_id(case, quarter), "key": key, "kind": kind, "text": text, "now": now},
        timeout_ms=WRITE_MS,
    )
    return get_draft(client, case, quarter, kind)  # type: ignore[return-value]


def get_draft(client: FalkorClient, case: Case, quarter: str, kind: str) -> dict | None:
    r = client.query(
        case.graph,
        "MATCH (d:Draft {key: $key}) RETURN properties(d)",
        {"key": f"draft:{note_id(case, quarter)}:{kind}"},
        timeout_ms=READ_MS,
    )
    return dict(r.result_set[0][0]) if r.result_set else None


def drafts_for(client: FalkorClient, case: Case, quarter: str) -> list[dict]:
    r = client.query(
        case.graph,
        "MATCH (d:Draft)-[:FOR]->(n:Note {id: $nid}) RETURN properties(d) ORDER BY d.kind LIMIT 20",
        {"nid": note_id(case, quarter)},
        timeout_ms=READ_MS,
    )
    return [dict(row[0]) for row in r.result_set]


def edit_draft(client: FalkorClient, case: Case, quarter: str, kind: str, text: str) -> bool:
    """Change the text of an unsent draft. A draft the owner marked sent is left alone."""
    r = client.query(
        case.graph,
        "MATCH (d:Draft {key: $key}) WHERE d.sent_by_owner = false SET d.text = $text RETURN d.key",
        {"key": f"draft:{note_id(case, quarter)}:{kind}", "text": text},
        timeout_ms=WRITE_MS,
    )
    return bool(r.result_set)


def mark_draft_sent(client: FalkorClient, case: Case, quarter: str, kind: str, now: int) -> bool:
    """The owner says they sent it themselves. True only for the first mark."""
    r = client.query(
        case.graph,
        "MATCH (d:Draft {key: $key})-[:FOR]->(n:Note) WHERE d.sent_by_owner = false "
        "SET d.sent_by_owner = true, d.sent_marked_at = $now, n.ack_at = coalesce(n.ack_at, $now) "
        "RETURN d.key",
        {"key": f"draft:{note_id(case, quarter)}:{kind}", "now": now},
        timeout_ms=WRITE_MS,
    )
    return bool(r.result_set)


# ---- Org: away flag and the named backup --------------------------------------------------------


def org_state(client: FalkorClient, case: Case) -> dict:
    r = client.query(
        case.graph,
        "MATCH (o:Org {id: $org}) OPTIONAL MATCH (o)-[b:BACKUP]->(a:Actor) "
        "RETURN o.owner_away, a.hid, b.named_by_owner_at",
        {"org": case.org},
        timeout_ms=READ_MS,
    )
    if not r.result_set:
        return {"away": False, "backup": None, "backup_named_at": None}
    away, hid, named = r.result_set[0]
    return {"away": bool(away), "backup": hid, "backup_named_at": named}


def set_away(client: FalkorClient, case: Case, away: bool, now: int) -> None:
    client.query(
        case.graph,
        "MERGE (o:Org {id: $org}) SET o.owner_away = $away, o.owner_away_at = $now",
        {"org": case.org, "away": away, "now": now},
        timeout_ms=WRITE_MS,
    )


def name_backup(client: FalkorClient, case: Case, hid: str, now: int) -> bool:
    """The one BACKUP edge of the org. False if no such Actor exists (nothing is written)."""
    exists = client.query(
        case.graph, "MATCH (a:Actor {hid: $hid}) RETURN a.hid", {"hid": hid}, timeout_ms=READ_MS
    )
    if not exists.result_set:
        return False
    client.query(
        case.graph,
        """MATCH (o:Org {id: $org}), (a:Actor {hid: $hid})
           OPTIONAL MATCH (o)-[old:BACKUP]->(x:Actor) WHERE x.hid <> $hid
           DELETE old
           MERGE (o)-[b:BACKUP]->(a)
           SET b.named_by_owner_at = coalesce(b.named_by_owner_at, $now)""",
        {"org": case.org, "hid": hid, "now": now},
        timeout_ms=WRITE_MS,
    )
    return True


def clear_backup(client: FalkorClient, case: Case) -> None:
    client.query(
        case.graph,
        "MATCH (:Org {id: $org})-[b:BACKUP]->(:Actor) DELETE b",
        {"org": case.org},
        timeout_ms=WRITE_MS,
    )


def keepers_as_of(client: FalkorClient, case: Case, T: int) -> list[str]:
    """Actors holding a sensitive Privilege by a GRANTED edge with at <= T."""
    r = run_as_of(
        client,
        case.graph,
        "MATCH (a:Actor)-[g:GRANTED]->(p:Privilege) WHERE g.at <= $T AND p.sensitive = true "
        "RETURN DISTINCT a.hid ORDER BY a.hid LIMIT 200",
        {"T": T},
        timeout_ms=READ_MS,
    )
    return [row[0] for row in r.result_set]


def flagged_for(client: FalkorClient, case: Case, quarter: str) -> list[str]:
    """Actors who asserted a PRESSURE, URGENCY or VOUCH claim that supports this Finding. Used
    only to keep them off the recipient list, never shown as a judgement."""
    r = client.query(
        case.graph,
        "MATCH (f:Finding {id: $fid})-[:SUPPORTED_BY]->(c:Claim)<-[:ASSERTED]-(a:Actor) "
        "WHERE c.kind IN $kinds RETURN DISTINCT a.hid ORDER BY a.hid LIMIT 200",
        {"fid": finding_id(case, quarter), "kinds": ["PRESSURE", "URGENCY", "VOUCH"]},
        timeout_ms=READ_MS,
    )
    return [row[0] for row in r.result_set]


def candidate_backups(client: FalkorClient, case: Case, T: int) -> list[str]:
    """The most active actors up to T, offered as suggestions when naming a backup."""
    r = run_as_of(
        client,
        case.graph,
        "MATCH (a:Actor)-[:DID]->(x:Action) WHERE x.at <= $T "
        "RETURN a.hid, count(x) AS n ORDER BY n DESC, a.hid LIMIT 8",
        {"T": T},
        timeout_ms=READ_MS,
    )
    return [row[0] for row in r.result_set]


# ---- Hardening nodes ----------------------------------------------------------------------------


def write_hardening(
    client: FalkorClient, case: Case, quarter: str, step: dict, run_ref: str
) -> None:
    key = f"hardening:{case.id}:{quarter}:{step['step']}"
    b, a = step["before"], step["after"]
    client.query(
        case.graph,
        """MERGE (h:Hardening {key: $key})
           SET h.step = $step, h.cost_before = $cb, h.cost_after = $ca,
               h.guardians_before = $gb, h.guardians_after = $ga,
               h.caught_before = $kb, h.caught_after = $ka,
               h.lead_before = $lb, h.lead_after = $la, h.run_ref = $ref
           WITH h MATCH (o:Org {id: $org}) MERGE (h)-[:FOR]->(o)""",
        {
            "key": key,
            "step": step["step"],
            "cb": b["takeover_cost"]["value"],
            "ca": a["takeover_cost"]["value"],
            "gb": b["guardians"]["value"],
            "ga": a["guardians"]["value"],
            "kb": step.get("caught", {}).get("before"),
            "ka": step.get("caught", {}).get("after"),
            "lb": step.get("lead_time", {}).get("before"),
            "la": step.get("lead_time", {}).get("after"),
            "ref": run_ref,
            "org": case.org,
        },
        timeout_ms=WRITE_MS,
    )


# ---- Tasks (thread questions) -------------------------------------------------------------------
# (write_task and tasks_for follow; the synthetic stamp wrapper is applied at the end of the file)


def write_task(
    client: FalkorClient,
    case: Case,
    quarter: str,
    *,
    key: str,
    question: str,
    answer: str,
    tool: str,
    refused: bool,
    input_version: str,
    now: int,
) -> bool:
    """A thread question becomes a Task, answered by the Investigator. True if newly created."""
    r = client.query(
        case.graph,
        """MATCH (n:Note {id: $nid})
           MERGE (t:Task {id: $id})
             ON CREATE SET t.kind = 'thread_question', t.status = 'DONE', t.priority = 5,
                           t.created_at = $now, t.claimed_by = 'investigator',
                           t.input_version = $iv, t.question = $q, t.answer = $a,
                           t.tool = $tool, t.refused = $refused
           MERGE (t)-[:FOR]->(n)""",
        {
            "nid": note_id(case, quarter),
            "id": f"task:{short(note_id(case, quarter) + '|' + key)}",
            "now": now,
            "iv": input_version,
            "q": question,
            "a": answer,
            "tool": tool,
            "refused": refused,
        },
        timeout_ms=WRITE_MS,
    )
    return r.nodes_created > 0


def tasks_for(client: FalkorClient, case: Case, quarter: str) -> list[dict]:
    r = client.query(
        case.graph,
        "MATCH (t:Task {kind: 'thread_question'})-[:FOR]->(n:Note {id: $nid}) "
        "RETURN properties(t) ORDER BY t.created_at, t.id LIMIT 200",
        {"nid": note_id(case, quarter)},
        timeout_ms=READ_MS,
    )
    return [dict(row[0]) for row in r.result_set]


# ---- Synthetic stamp ----------------------------------------------------------------------------
# org_tallowdate holds only synthetic entities (CLAUDE.md): every node and edge carries
# synthetic: true, and a test checks it. Every write below leaves that true for a synthetic case.


def stamp_synthetic(client: FalkorClient, graph: str) -> None:
    client.query(
        graph, "MATCH (n) WHERE n.synthetic IS NULL SET n.synthetic = true", timeout_ms=WRITE_MS
    )
    client.query(
        graph,
        "MATCH ()-[r]->() WHERE r.synthetic IS NULL SET r.synthetic = true",
        timeout_ms=WRITE_MS,
    )


def _stamped(fn):
    @functools.wraps(fn)
    def wrapper(client, case, *args, **kwargs):
        out = fn(client, case, *args, **kwargs)
        if case.synthetic:
            stamp_synthetic(client, case.graph)
        return out

    return wrapper


for _name in (
    "sync_case",
    "set_route",
    "mark",
    "agent_step",
    "record_dismissal",
    "link_learned",
    "snooze",
    "create_draft",
    "edit_draft",
    "mark_draft_sent",
    "set_away",
    "name_backup",
    "clear_backup",
    "write_hardening",
    "write_task",
):
    globals()[_name] = _stamped(globals()[_name])


def findings_present(client: FalkorClient, case: Case) -> int:
    r = client.query(
        case.graph,
        "MATCH (f:Finding {case: $case}) RETURN count(f)",
        {"case": case.id},
        timeout_ms=READ_MS,
    )
    return r.result_set[0][0]
