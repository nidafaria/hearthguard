.PHONY: video-check ecosystem-xz inbox slack-preview harden-xz hardening-fixture tallowdate-run synthetic-tallowdate reader-full pressure-vouch-xz quarterly-xz decision-xz ui up down test lint smoke-algos schema-test ingest-xz normal-xz takeover-xz detectors-xz cache-mail-xz cache-github-xz cache-inventory-xz llm-test reader-spotcheck reader-testset reader-score gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race

# Working targets. On Windows without make, use: .\make.ps1 <target>
up:
	docker compose up -d

down:
	docker compose down

# pytest exits 5 when it collects zero tests. That is fine at this stage, so map 5 to 0 and say so.
test:
	uv run pytest; rc=$$?; if [ $$rc -eq 5 ]; then echo "pytest: 0 tests collected"; exit 0; fi; exit $$rc

lint:
	uv run ruff check .
	uv run ruff format --check .

# Re-checks every FalkorDB procedure the product depends on, on the pinned image (exit 1 on any failure).
smoke-algos:
	uv run pytest tests/integration/test_smoke_algos.py -s -v

# Schema, as-of helper, read-only guard and hashing: real FalkorDB, plus pure unit checks.
schema-test:
	uv run pytest tests/integration/test_schema.py tests/integration/test_as_of.py tests/integration/test_ro_guard.py tests/unit -v

# Ingest the public xz git history into org_xz (loads twice and checks the counts match).
ingest-xz:
	uv run python -m packs.oss.ingest_xz --twice

# Remembered-normal metrics for xz at each quarter-end -> eval/results/xz_normal.json
normal-xz:
	uv run python -m eval.xz_normal

# Takeover cost and guardians on org_xz: expected NOT COMPUTED (git has no grant record).
takeover-xz:
	uv run python -m eval.xz_takeover_status

# Rush, Bypass and Lone keeper on org_xz: expected NOT_COMPUTED (no grant data, thin release path).
detectors-xz:
	uv run python -m eval.xz_detector_status

# Public xz data cache (data/raw, git-ignored). Nothing here touches the graph.
cache-mail-xz:
	uv run python -m packs.oss.cache_xz_raw mail

# Slow without GITHUB_TOKEN in .env (60 requests an hour). Safe to stop and rerun: it skips what is cached.
cache-github-xz:
	uv run python -m packs.oss.cache_xz_raw github

cache-inventory-xz:
	uv run python -m packs.oss.cache_xz_raw inventory

# One live call to the extraction model. Needs GROQ_API_KEY in .env. Prints status, JSON parse and tokens.
llm-test:
	uv run python -m eval.llm_connection_test

# The Reader on 20 fixed xz-devel messages (live Groq, cached). Writes eval/results/reader_*.json.
reader-spotcheck:
	uv run python -m eval.reader_spotcheck

# Reader test set: check the freeze, pick the messages by the fixed rule, write the labelling sheet.
# A year with fewer than 15 messages needs an explicit choice: READER_SHORTFALL=keep or top-up.
reader-testset:
	uv run python -m eval.reader_freeze
	uv run python -m eval.reader_testset

# Score the frozen Reader against the human labels (runs the Reader once if it has not been run).
# Refuses, and lists the rows, if any label is missing.
reader-score:
	uv run python -m eval.reader_score

# The Reader on every in-scope xz-devel message except the human-labelled test set. Resumable: it
# stops at the daily token limit and picks up on the next run. Needs GROQ_API_KEY.
reader-full:
	uv run python -m eval.reader_full_run

# Claims into org_xz, then Pressure and Vouch at each quarter-end. Needs FalkorDB.
pressure-vouch-xz:
	uv run python -m eval.xz_pressure_vouch_status

# Rush, Bypass, Lone keeper, takeover cost and guardians at each quarter-end. Needs FalkorDB.
quarterly-xz:
	uv run python -m eval.xz_quarterly_status

# The decision policy on the saved statuses. Reads files only.
decision-xz:
	uv run python -m eval.xz_decision_status

# The local inbox, not connected to Slack. Builds the UI, then serves it at http://127.0.0.1:8765/#/inbox
inbox:
	cd ui && npm install --no-audit --no-fund && npm run build && cd .. && uv run python -m api.serve

# The Slack note and "Show me why" text for each quarter, from saved results only. Nothing is sent.
slack-preview:
	uv run python -m slack_app.render

# Replay from saved results only: make replay CASE=xz. Writes eval/results/xz_replay.json and .md.
replay:
	uv run python -m eval.replay_$(or $(CASE),xz)

# Hardening simulator on fixture graphs -> eval/results/hardening_fixture.json (needs FalkorDB up).
hardening-fixture:
	uv run python -m core.hardening.simulate

# Hardening on org_xz, every quarter-end and OSS menu step -> eval/results/xz_hardening.json (needs FalkorDB up).
harden-xz:
	uv run python -m core.hardening.xz

# The demo: the same replay table, from saved results only. No network, no key, no FalkorDB.
demo:
	uv run python -m eval.demo

# The whole tallowdate pipeline, steps 1-5, in order. Needs FalkorDB and .env. Prints PASS/FAIL per step.
tallowdate-run:
	uv run python -m redteam.run_tallowdate

# The fictional tallowdate history (synthetic, labelled). Writes data/synthetic/tallowdate.json. Generate only.
synthetic-tallowdate:
	uv run python -m redteam.tallowdate

# The demo video package: every quote matched word for word in the cached mail, every number read from
# eval/results/*.json, timing, Act II labels and narration. Exit 1 on any failure. Writes eval/results/video_*.json.
video-check:
	uv run python -m eval.video_check

# The read-only page over eval/results/*.json. Needs no key and no FalkorDB.
ui:
	cd ui && npm install && npm run dev

# Placeholders for later steps. Each one fails until it is built.
gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race:
	@echo "$@: not built yet"
	@exit 1

# Fetch the public xz ecosystem records, load ecosystem_xz twice, compute visibility gaps (no model calls).
ecosystem-xz:
	uv run python -m eval.ecosystem_xz
