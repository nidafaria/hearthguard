# Blockers: inbox, Slack note sending, note safety (branch coding/inbox-safety)

Rows below stay open. Nothing here was marked DONE by hand. Only `eval/completion_full.py` may do that.

## Row 22: Maintainer private note (§4.3)
- Requirement: the maintainer gets one private note in Slack, as a question.
- Built: the web inbox, and the send path `slack_app/notify.py` against an injected sender, tested with a fake.
- Blocked by: the real Slack sender needs a Slack workspace, a bot token and the owner's Slack user id in `.env`. A person must create these. No message may go to a real workspace from this task.
- Unblock: see `eval/results/blockers_slack_sender.md`.

## Row 25: Controller note with Mark callback done (finance, §4.3, §12.2)
- Requirement: the finance lead gets the note, and a **Mark callback done** button records `Path.verified = true`, so the Bypass resolves from the system record and the note turns grey.
- Built (this branch): `core/agents/callback.py` `mark_callback_done`, tested on a real FalkorDB in `tests/integration/test_callback_done.py`. It writes the verification once per action, a double tap changes nothing, and only bank changes can be marked. The unchanged Bypass detector then reports the callback property as MATCHES.
- Measured, not assumed: on the Northbridge case, channel and approvers still differ after the tap, so the Bypass as a whole still FIRES on those two. Only the callback property resolves.
- Blocked by: (1) the finance note text is a Liaison wording step, which is an LLM step (`eval/results/blockers_H.md` row 94); (2) the Slack sender, as for row 22; (3) the finance pack is not a case in the web inbox (`core/agents/cases.py` has xz and tallowdate only), so there is no button or grey note to wire. Adding a case needs a decision on which saved decision file the finance note reads, and none exists.

## Row 38: org graph node set (§6.1)
- Requirement: Finding, Gap, Objection, Request, Note, Draft, OwnerDecision, BACKUP.
- Built (this branch): `tests/integration/test_objection_request.py` covers `add_objection` and `add_request` (stored, idempotent, nothing written for a missing parent).
- Blocked by: there is no Skeptic agent, so nothing calls the writers in a real run (`eval/results/blockers_a.md`). The Skeptic's benign-explanation search is an LLM step.

## Row 100: Slack app (Bolt, Socket Mode) sends the note (§12.2)
- Requirement: a Bolt app in Socket Mode sends the note.
- Built: render, and the send path against a fake sender.
- Blocked by: no workspace, no app token, no bot token, and no Bolt dependency. A real send is not allowed from this task.
- Unblock: see `eval/results/blockers_slack_sender.md`.
