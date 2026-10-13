# Remaining agent work, divided into five blocks

Open rows on main: 80 (PARTIAL 35, NOT STARTED 45). Agent-doable: 33. Set aside (see remaining_not_agent.md): 47.

Effort figures are estimates in working hours. They are larger than CLAUDE.md's 90-minute step guideline, so each block is a multi-hour session.

| Block | Name | Rows | Model | Branch | FalkorDB port | Estimate (h) |
|---|---|---|---|---|---|---|
| E | Learning and owner memory | 43, 66, 75, 80, 102, 104, 120 | Sonnet | agent/block-E | 6382 | 10 |
| F | Task board and resilience | 39, 65, 69, 76, 79, 81 | Sonnet | agent/block-F | 6383 | 8.5 |
| G | Ingest, ecosystem and docs | 4, 6, 15, 19, 40, 84, 128 | Sonnet | agent/block-G | 6384 | 10.5 |
| H | Finance pack and visibility graph | 17, 18, 21, 35, 45, 74, 94, 98 | Sonnet | agent/block-H | 6385 | 10.5 |
| I | Evaluation and MCP servers | 78, 82, 96, 97, 117 | Haiku | agent/block-I | 6386 | 8 |

## Files each block owns

### Block E: Learning and owner memory
- core/learning/** (new files)
- core/playbook/** (new files)
- core/agents/inbox_graph.py
- core/agents/simulate_fix.py
- api/inbox_actions.py
- ui/src/Thread.tsx
- ui/src/Playbook.tsx (new)
- ui/src/App.tsx (route for the Playbook screen only)
- tests/unit/test_learning_*.py (new)
- tests/integration/test_learning_*.py (new)
- tests/integration/test_inbox_loop.py
- eval/verify_learning.py (new)
- eval/chaos.py (new)
- eval/results/learning_*.json (new)
- docs/decisions/0007-learned-exception-filler.md (new)

### Block F: Task board and resilience
- core/board/** (new files)
- core/agents/guardrails.py (new)
- core/agents/agent_step.py (new)
- tests/determinism/** (new files)
- tests/race/** (new files)
- tests/faults/** (new files)
- tests/unit/test_board_*.py (new)
- tests/integration/test_board_*.py (new)
- tests/unit/test_guardrails_*.py (new)
- eval/verify_determinism.py (new)
- eval/race.py (new)
- eval/concurrency.py (new)
- eval/faults.py (new)
- eval/results/determinism_*.json, race_*.json, concurrency_*.json, faults_*.json (new)

### Block G: Ingest, ecosystem and docs
- packs/oss/** (all of it)
- eval/ecosystem*.py
- eval/incidents_*.py (new)
- eval/replay_event_stream.py (new)
- eval/replay_axios.py (new)
- eval/video_check.py and eval/blog_check.py (lint fixes only)
- README.md
- tests/integration/test_ecosystem_xz.py
- tests/integration/test_incidents_*.py (new)
- tests/unit/test_oss_parsers_*.py (new)
- eval/results/incidents_*.json, replay_event_stream.json, replay_axios.json (new)
- eval/results/ecosystem_*.json (only the files this block regenerates)

### Block H: Finance pack and visibility graph
- packs/finance/** (new files)
- mcp_servers/pack-finance/** (new)
- eval/verify_packs.py (new)
- eval/northbridge_case.py (new)
- data/synthetic/northbridge*.json (new)
- core/memory/who_saw.py
- eval/populate_visibility.py (new)
- core/graph/schema.py
- eval/vector_index.py (new)
- tests/unit/test_finance_*.py (new)
- tests/integration/test_finance_*.py (new)
- tests/integration/test_visibility_*.py (new)
- tests/integration/test_vector_index.py (new)
- docs/VERIFIED.md (append only)
- eval/results/finance_*.json, visibility_*.json, vector_index_*.json (new)

### Block I: Evaluation and MCP servers
- eval/ablation_memory.py (new)
- eval/ablation_algos.py (new)
- eval/results/ablation_memory.json, ablation_algos.json (new)
- ui/src/Patience.tsx
- mcp_servers/hearthguard-core/** (new)
- mcp_servers/pack-oss/** (new)
- tests/unit/test_mcp_*.py (new)
- tests/integration/test_ablation_*.py (new)
- tests/integration/test_mcp_*.py (new)

## Shared files (owned by no block; the lead edits them on main after the merges)
- Makefile and make.ps1: targets for verify-learning, chaos, ablation-memory, ablation-algos, verify-determinism, race, concurrency, faults, verify-packs, and replay for event-stream and axios.
- docs/AI_USE.md: the lead appends each block's line from eval/results/ai_use_<letter>.md.
- eval/completion_full.py and eval/results/completion_full.json and .md: regenerated on main after each merge.
- docs/HEARTHGUARD.md, docs/FREEZE.md, docs/FREEZE.sha256: not edited by any block.

## Dependencies (all inside one block; none cross blocks)
- 80 needs 66 and 43; 104 needs 66; 120 needs 43 and 66 (block E).
- 79 needs 65; 81 needs 69; 39 and 76 share the task board (block F).
- 84 needs 15 and the replay code; 19 and 40 share packs/oss (block G).
- 98 needs 21 (block H).
- 117 needs 78 (block I).

## Known gaps in this plan
- eval/results/blockers_c.md is not on main (it was on a branch that was not merged), so block C's blocker notes for rows 85 and 117 are not in the prompts.
- Row 6's lint failure in eval/completion_full.py (E402, I001) is in a file no block owns; the lead fixes it on main.
