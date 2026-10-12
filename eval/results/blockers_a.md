# Block A blockers

Rows still PARTIAL after the completion re-run. Each one names what is missing. No command failed
for these rows; they are unbuilt parts of the spec, not errors. The check commands below show the
current state.

| Row | Item | Why it is not DONE | Check |
|---|---|---|---|
| 22 | Maintainer private note (§4.3) | The note and its controls exist in the web inbox only. The Slack DM (§4.3, §12.2) is not built, and the brief said nothing is sent to Slack. | `ls slack_app` (no sender module) |
| 38 | org graph node set (§6.1) | Finding, Note, Draft, OwnerDecision, BACKUP, Gap and Hardening are written. Objection and Request have writer functions (`core/agents/inbox_graph.py` add_objection, add_request) but no source: there is no Skeptic in this repo, and nothing calls them. No test covers them. | `uv run python -c "from core.agents import inbox_graph as g; print(g.add_objection)"` |
| 61 | Investigator (§8.1) | Thread questions use a fixed tool router with no LLM. The spec calls for an LLM planner and an MCP tools/list. The no-LLM choice is recorded as OPEN in docs/decisions/0008-inbox-no-llm.md because the Groq allowance is used up. | `docs/decisions/0008-inbox-no-llm.md` |
| 63 | Liaison (§8.1) | Note, replies, drafts and snooze are built for the web inbox. Missing: the Slack sender, learned-exception proposals from dismissals (§8.3), and LLM note wording. | `core/agents/liaison.py` |
| 75 | Owner memory (§9) | OwnerDecision is written once per finding. The rule that a dismissed situation does not come back without new evidence is not built. | `core/agents/inbox_graph.py` record_dismissal |
| 102 | Simulate a fix button (§12.2) | Live simulate runs and shows cost and guardians. Caught and lead time show NOT COMPUTED, because no saved red-team result file exists on main. Block C may add one. | `ls eval/results/redteam*.json` (no match on this branch) |
| 109 | Slack safety tests (§12.2) | Injection and double-tap tests pass. There is no Slack code in this build, so there is no real Slack-down test; the inbox-without-Slack test checks flags only. | `tests/integration/test_inbox_loop.py` |

## Other notes for the owner

- Block A's browser check used the local app on port 8766. A separate server was already bound to
  port 8765 from another checkout; I did not stop it.
- `make inbox` (port 8765) will serve the old build until that other process stops.
- The older Simulate and Dismiss controls were removed from ui/src/Inbox.tsx after the browser check. The Thread controls remain.
