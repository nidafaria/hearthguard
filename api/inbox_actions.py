"""The note loop for the web inbox (spec 12.2): why, simulate, draft, dismiss, snooze, thread
questions, routing and the weekly digest. Mounted from api/app.py. Nothing is sent to Slack or to
any person. Every response says whether its data is the public xz record or the synthetic
tallowdate case.

State lives in the org graph (core/agents/inbox_graph.py). Saved results come from eval/results.
If the graph cannot be reached the endpoints answer 503 and say so; nothing is faked.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from core.agents import digest, investigator, liaison, routing, simulate_fix, why
from core.agents import inbox_graph as ig
from core.agents.cases import CASES, RESULTS, Case, iso, normalize_rows, read_json
from core.graph.client import FalkorClient
from core.hardening import simulate as sim
from core.learning import pipeline as learning
from core.learning import states
from core.playbook import store as playbook

QUARTER = r"^\d{4}-Q[1-4]$"
OWNER = "owner"


class Reason(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class DraftRequest(BaseModel):
    kind: str = "boundary_reply"


class DraftEdit(BaseModel):
    kind: str = "boundary_reply"
    text: str = Field(min_length=1, max_length=2000)


class RoutingChange(BaseModel):
    away: bool | None = None
    backup: str | None = Field(default=None, max_length=128)
    clear_backup: bool = False


def _result_line(out: dict) -> str:
    """The line the thread shows (spec 12.2): what was tested, and what came of it."""
    g = out["gate"]
    if g is None:
        return f"{out['state']}: {out['state_reason']}"
    if g["planted_lost"]:
        return f"rejected: it would have hidden {g['planted_lost']} of {g['planted_total']} attacks"
    if not g["passed"]:
        return f"rejected: {g['reason']}"
    return (
        f"tested against {g['planted_total']} planted attacks, {g['planted_lost']} lost "
        f"— {out['state'].lower()}"
    )


def build_router(
    results: Path = RESULTS,
    inbox_file: Path | None = None,
    client: FalkorClient | None = None,
    now: Callable[[], int] | None = None,
    cases: dict[str, Case] | None = None,
    playbook_graph: str = playbook.GRAPH,
) -> APIRouter:
    client = client or FalkorClient()
    clock = now or (lambda: int(time.time()))
    case_map = cases or CASES
    if inbox_file is None:
        inbox_file = Path(__file__).resolve().parent.parent / "data" / "inbox" / "dismissals.jsonl"
    router = APIRouter(prefix="/api/inbox")
    synced: dict[str, int] = {}
    lock = threading.Lock()
    suite_cache: dict[str, tuple[list[dict], list[dict]]] = {}

    def suite() -> tuple[list[dict], list[dict]]:
        """The saved red-team suite and real-case rows the regression gate replays (read once)."""
        if "suite" not in suite_cache:
            suite_cache["suite"] = learning.load_suite(results)
        return suite_cache["suite"]

    def learn_from(case: Case, quarter: str, reason: str) -> dict:
        """Dismissal -> proposal -> safety rules -> regression gate -> end state (spec 12.2).
        Runs once per dismissal: a repeat tap returns what was stored, and counts no agreement."""
        done = ig.learned_for(client, case, quarter)
        if done is not None:
            return {"new": False, **done, "playbook": _stored(done["exception_id"])}
        campaigns, real_rows = suite()
        t = clock()
        out = learning.learn(reason, campaigns, real_rows, agreements=1)
        stored = None
        xid = out["exception_id"]
        if xid is not None:
            prior = playbook.get(client, xid, playbook_graph)
            agreements = playbook.count_agreement(client, xid, t, playbook_graph) if prior else 1
            approved = bool(prior and prior.get("owner_approved_at"))
            if prior:
                out = learning.learn(
                    reason, campaigns, real_rows, agreements=agreements, owner_approved=approved
                )
            stored = playbook.record(client, out, t, playbook_graph)
        ig.link_learned(client, case, quarter, xid, out["state"], out["state_reason"])
        return {
            "new": True,
            "exception_id": xid,
            "state": out["state"],
            "state_reason": out["state_reason"],
            "template": out["template"],
            "attempts": out["attempts"],
            "safety": out["safety"],
            "gate": out["gate"],
            "playbook": stored,
            "nothing_is_applied": True,
            "result_line": _result_line(out),
        }

    def _stored(xid: str | None) -> dict | None:
        return playbook.get(client, xid, playbook_graph) if xid else None

    def case_of(case_id: str) -> Case:
        if case_id not in case_map:
            raise HTTPException(404, "no such case")
        return case_map[case_id]

    def ensure(case_id: str) -> tuple[Case, list[dict]]:
        """Write the Finding and Note nodes once per version of the saved decision file."""
        case = case_of(case_id)
        stamp = (results / case.decision_file).stat().st_mtime_ns
        rows = normalize_rows(case, results)
        with lock:
            try:
                # Re-sync when the saved file changed or the graph lost its findings (reload).
                if synced.get(case_id) != stamp or ig.findings_present(client, case) != len(rows):
                    ig.sync_case(client, case, rows, results, clock)
                    synced[case_id] = stamp
            except (RedisError, OSError, TimeoutError) as e:
                raise HTTPException(
                    503, f"the graph could not be reached ({type(e).__name__}); run make up"
                ) from e
        return case, rows

    def locate(case_id: str, quarter: str) -> tuple[Case, dict]:
        import re

        if not re.match(QUARTER, quarter):
            raise HTTPException(404, "no such note")
        case, rows = ensure(case_id)
        for r in rows:
            if r["quarter"] == quarter:
                return case, r
        raise HTTPException(404, "no such note")

    def head(case: Case) -> dict:
        return {
            "label": case.label,
            "case": case.id,
            "data_kind": case.kind_word,
            "synthetic": case.synthetic,
            "connected_to_slack": False,
            "sent_to_slack": False,
        }

    def route_for(case: Case, row: dict, state: dict) -> dict:
        org = ig.org_state(client, case)
        n = state["note"]
        r = routing.route_note(
            owner=OWNER,
            keepers=ig.keepers_as_of(client, case, row["T"]),
            backup=org["backup"],
            away=org["away"],
            created_at=n.get("created_at", clock()),
            ack_at=n.get("ack_at"),
            now=clock(),
            flagged=ig.flagged_for(client, case, row["quarter"]),
        )
        if n.get("routed_to_hid") != r.recipients[0] or n.get("thread_hids") != list(r.recipients):
            ig.set_route(client, case, row["quarter"], list(r.recipients))
        return {
            "recipients": [x if x == OWNER else x[:8] + " (hashed)" for x in r.recipients],
            "thread": r.thread,
            "backup_used": r.backup_used,
            "waiting": r.waiting,
            "reason": r.reason,
            "owner_away": org["away"],
            "backup": org["backup"][:8] + " (hashed)" if org["backup"] else None,
            "hours_to_backup": routing.UNACKED_HOURS,
            "nothing_is_sent": True,
        }

    @router.get("/cases")
    def list_cases() -> dict:
        out = []
        for cid in case_map:
            case, rows = ensure(cid)
            out.append(
                {
                    "case": cid,
                    "label": case.label,
                    "synthetic": case.synthetic,
                    "data_kind": case.kind_word,
                    "notes": len(rows),
                }
            )
        return {"cases": out, "connected_to_slack": False, "sent_to_slack": False}

    @router.get("/{case_id}/notes")
    def list_notes(case_id: str) -> dict:
        case, rows = ensure(case_id)
        items = []
        for row in rows:
            state = ig.note_state(client, case, row["quarter"])
            snooze = liaison.snooze_status(
                state["note"].get("snoozed_until"),
                state["note"].get("snoozed_moves"),
                liaison.fired_moves(row),
                clock(),
            )
            items.append(
                {
                    "quarter": row["quarter"],
                    "decision": row["decision"],
                    "headline": liaison.headline(case, row),
                    "status": state["finding"]["status"],
                    "dismissed": state["finding"]["status"] == "dismissed",
                    "snooze": snooze["state"],
                }
            )
        return {**head(case), "notes": items}

    @router.get("/{case_id}/notes/{quarter}")
    def thread(case_id: str, quarter: str) -> dict:
        case, row = locate(case_id, quarter)
        state = ig.note_state(client, case, quarter)
        n = state["note"]
        snooze = liaison.snooze_status(
            n.get("snoozed_until"), n.get("snoozed_moves"), liaison.fired_moves(row), clock()
        )
        return {
            **head(case),
            "quarter": quarter,
            "decision": row["decision"],
            "as_of": row["T_iso"],
            "note": liaison.note_text(case, row),
            "controls": list(liaison.CONTROLS),
            "finding": {
                "id": state["finding"]["id"],
                "status": state["finding"]["status"],
                "moves": state["finding"].get("moves"),
            },
            "note_state": {
                k: n.get(k)
                for k in ("created_at", "opened_at", "ack_at", "snoozed_until", "routed_to_hid")
            },
            "snooze": snooze,
            "routing": route_for(case, row, state),
            "decisions": ig.owner_decisions(client, case, quarter),
            "drafts": ig.drafts_for(client, case, quarter),
            "questions": ig.tasks_for(client, case, quarter),
            "suggested_questions": list(investigator.SUPPORTED),
        }

    @router.get("/{case_id}/notes/{quarter}/why")
    def show_why(case_id: str, quarter: str) -> dict:
        case, row = locate(case_id, quarter)
        t = clock()
        ig.mark(client, case, quarter, "opened_at", t)
        try:
            doc = why.build_why(client, case, row, results)
        except ValueError as e:
            raise HTTPException(500, str(e)) from e
        ig.agent_step(
            client,
            case,
            quarter,
            agent="liaison",
            tool="why",
            reason="Show me why",
            ms=doc["live_query"]["ms"],
            result_ref=ig.finding_id(case, quarter),
            now=t,
            step_key=str(time.time_ns()),
        )
        return {
            **head(case),
            "quarter": quarter,
            "decision": row["decision"],
            "as_of": row["T_iso"],
            **doc,
            "note": "Facts and reasons are from saved status files; quotes and links are from "
            "the graph, read live. Nothing here judges a person.",
        }

    @router.post("/{case_id}/notes/{quarter}/simulate")
    def simulate(case_id: str, quarter: str) -> dict:
        case, row = locate(case_id, quarter)
        t = clock()
        try:
            doc = simulate_fix.simulate_steps(client, case, row, results)
        except (RedisError, OSError, TimeoutError) as e:
            raise HTTPException(503, f"the simulation could not run ({type(e).__name__})") from e
        ig.mark(client, case, quarter, "opened_at", t)
        ig.agent_step(
            client,
            case,
            quarter,
            agent="liaison",
            tool="simulate",
            reason="Simulate a fix",
            ms=doc["total_ms"],
            result_ref=f"live:{case.id}:{quarter}",
            now=t,
            step_key=str(time.time_ns()),
        )
        return {**head(case), "quarter": quarter, "menu": list(sim.MENU), **doc}

    @router.post("/{case_id}/notes/{quarter}/dismiss")
    def dismiss(case_id: str, quarter: str, body: Reason) -> dict:
        case, row = locate(case_id, quarter)
        reason = body.reason.strip()
        if len(reason) < 3:
            raise HTTPException(422, "a reason of at least 3 characters is required")
        out = liaison.dismiss(client, case, row, reason, clock(), inbox_file)
        try:
            learned = learn_from(case, quarter, out["dismissal"]["reason"])
        except (RedisError, OSError, TimeoutError) as e:
            raise HTTPException(503, f"the learning step could not run ({type(e).__name__})") from e
        return {**head(case), "quarter": quarter, **out, "learning": learned}

    @router.get("/playbook")
    def show_playbook() -> dict:
        try:
            doc = playbook.list_exceptions(client, playbook_graph)
        except (RedisError, OSError, TimeoutError) as e:
            raise HTTPException(503, f"the playbook could not be read ({type(e).__name__})") from e
        return {"synthetic": False, "data_kind": "playbook (no organisation data)", **doc}

    @router.post("/playbook/{xid}/approve")
    def approve_exception(xid: str) -> dict:
        if not xid.startswith("exc:"):
            raise HTTPException(404, "no such exception")
        out = playbook.approve(client, xid, clock(), playbook_graph)
        if out is None:
            raise HTTPException(409, "only a Shadow exception can be approved, and only once")
        return {"exception": out, "state": states.ADOPTED}

    @router.post("/{case_id}/notes/{quarter}/snooze")
    def snooze_note(case_id: str, quarter: str) -> dict:
        case, row = locate(case_id, quarter)
        out = liaison.remind_in_a_week(client, case, row, clock())
        n = ig.note_state(client, case, quarter)["note"]
        status = liaison.snooze_status(
            n.get("snoozed_until"), n.get("snoozed_moves"), liaison.fired_moves(row), clock()
        )
        return {**head(case), "quarter": quarter, **out, "snooze": status}

    @router.post("/{case_id}/notes/{quarter}/draft")
    def make_draft(case_id: str, quarter: str, body: DraftRequest) -> dict:
        case, _row = locate(case_id, quarter)
        try:
            text = liaison.draft_text(body.kind)
        except KeyError as e:
            raise HTTPException(422, str(e)) from e
        existing = ig.get_draft(client, case, quarter, body.kind)
        draft = existing or ig.create_draft(client, case, quarter, body.kind, text, clock())
        return {
            **head(case),
            "quarter": quarter,
            "already": existing is not None,
            "draft": draft,
            "kinds": sorted(liaison.DRAFT_KINDS),
            "reminder": "Edit it, then send it yourself. Hearthguard contacts no one.",
        }

    @router.put("/{case_id}/notes/{quarter}/draft")
    def edit_draft(case_id: str, quarter: str, body: DraftEdit) -> dict:
        case, _row = locate(case_id, quarter)
        if ig.get_draft(client, case, quarter, body.kind) is None:
            raise HTTPException(404, "no draft yet: use Draft a reply first")
        changed = ig.edit_draft(client, case, quarter, body.kind, body.text)
        return {
            **head(case),
            "quarter": quarter,
            "saved": changed,
            "draft": ig.get_draft(client, case, quarter, body.kind),
        }

    @router.post("/{case_id}/notes/{quarter}/draft/sent")
    def draft_sent(case_id: str, quarter: str, body: DraftRequest) -> dict:
        case, _row = locate(case_id, quarter)
        if ig.get_draft(client, case, quarter, body.kind) is None:
            raise HTTPException(404, "no draft yet: use Draft a reply first")
        first = ig.mark_draft_sent(client, case, quarter, body.kind, clock())
        return {
            **head(case),
            "quarter": quarter,
            "already": not first,
            "draft": ig.get_draft(client, case, quarter, body.kind),
            "reminder": "This only records that you sent it yourself. Nothing was sent.",
        }

    @router.post("/{case_id}/notes/{quarter}/ask")
    def ask(case_id: str, quarter: str, body: Question) -> dict:
        case, row = locate(case_id, quarter)
        question = body.question.strip()
        t = clock()
        try:
            ans = investigator.answer(client, case, row, question, results)
        except ValueError as e:
            raise HTTPException(500, str(e)) from e
        doc = read_json(results / case.decision_file)
        created = ig.write_task(
            client,
            case,
            quarter,
            key=investigator.normalize_question(question),
            question=question,
            answer=ans.text,
            tool=ans.tool,
            refused=ans.refused,
            input_version=str(doc.get("generated_at_utc", "unknown")),
            now=t,
        )
        ig.agent_step(
            client,
            case,
            quarter,
            agent="investigator",
            tool=ans.tool,
            reason="thread question",
            ms=ans.ms,
            result_ref=ig.finding_id(case, quarter),
            now=t,
            step_key=investigator.normalize_question(question),
        )
        return {
            **head(case),
            "quarter": quarter,
            "question": question,
            "answer": ans.text,
            "tool": ans.tool,
            "refused": ans.refused,
            "links": ans.links,
            "ms": ans.ms,
            "already": not created,
            "llm_calls": 0,
        }

    @router.get("/{case_id}/digest")
    def weekly_digest(case_id: str) -> dict:
        case = case_of(case_id)
        return {**head(case), **digest.build_digest(case, results)}

    @router.get("/{case_id}/routing")
    def routing_state(case_id: str) -> dict:
        case, rows = ensure(case_id)
        org = ig.org_state(client, case)
        latest = max(rows, key=lambda r: r["T"])
        return {
            **head(case),
            "owner_away": org["away"],
            "backup": org["backup"],
            "backup_named_at": org["backup_named_at"],
            "candidates": ig.candidate_backups(client, case, latest["T"]),
            "as_of": iso(latest["T"]),
        }

    @router.post("/{case_id}/routing")
    def change_routing(case_id: str, body: RoutingChange) -> dict:
        case, _rows = ensure(case_id)
        t = clock()
        if body.away is not None:
            ig.set_away(client, case, body.away, t)
        if body.clear_backup:
            ig.clear_backup(client, case)
        elif body.backup:
            if not ig.name_backup(client, case, body.backup.strip(), t):
                raise HTTPException(422, "that id is not an actor in this graph")
        return routing_state(case_id)

    return router
