.PHONY: up down test lint smoke-algos demo replay gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race

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

# Placeholders for later steps. Each one fails until it is built.
smoke-algos demo replay gaps harden redteam ablation-memory ablation-algos false-positives eval-reader verify-frozen verify-determinism race:
	@echo "$@: not built yet"
	@exit 1
