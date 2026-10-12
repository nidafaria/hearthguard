.PHONY: up down test lint smoke-algos schema-test ingest-xz normal-xz takeover-xz detectors-xz cache-mail-xz cache-github-xz cache-inventory-xz llm-test demo replay gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race

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

# Placeholders for later steps. Each one fails until it is built.
demo replay gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race:
	@echo "$@: not built yet"
	@exit 1
