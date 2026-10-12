# Windows fallback for the Makefile. Usage: .\make.ps1 <target>   (targets: up, down, test, lint)
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "test", "lint", "smoke-algos", "schema-test", "ingest-xz", "normal-xz", "takeover-xz", "detectors-xz", "cache-mail-xz", "cache-github-xz", "cache-inventory-xz", "llm-test", "reader-spotcheck", "help")]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"

switch ($Target) {
    "up" {
        docker compose up -d
    }
    "down" {
        docker compose down
    }
    "test" {
        uv run pytest
        # pytest exits 5 when it collects zero tests. That is fine at this stage.
        if ($LASTEXITCODE -eq 5) {
            Write-Host "pytest: 0 tests collected"
            exit 0
        }
        exit $LASTEXITCODE
    }
    "lint" {
        uv run ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run ruff format --check .
        exit $LASTEXITCODE
    }
    "smoke-algos" {
        uv run pytest tests/integration/test_smoke_algos.py -s -v
        exit $LASTEXITCODE
    }
    "schema-test" {
        uv run pytest tests/integration/test_schema.py tests/integration/test_as_of.py tests/integration/test_ro_guard.py tests/unit -v
        exit $LASTEXITCODE
    }
    "ingest-xz" {
        uv run python -m packs.oss.ingest_xz --twice
        exit $LASTEXITCODE
    }
    "normal-xz" {
        uv run python -m eval.xz_normal
        exit $LASTEXITCODE
    }
    "takeover-xz" {
        uv run python -m eval.xz_takeover_status
        exit $LASTEXITCODE
    }
    "detectors-xz" {
        uv run python -m eval.xz_detector_status
        exit $LASTEXITCODE
    }
    "cache-mail-xz" {
        uv run python -m packs.oss.cache_xz_raw mail
        exit $LASTEXITCODE
    }
    "cache-github-xz" {
        uv run python -m packs.oss.cache_xz_raw github
        exit $LASTEXITCODE
    }
    "cache-inventory-xz" {
        uv run python -m packs.oss.cache_xz_raw inventory
        exit $LASTEXITCODE
    }
    "llm-test" {
        uv run python -m eval.llm_connection_test
        exit $LASTEXITCODE
    }
    "reader-spotcheck" {
        uv run python -m eval.reader_spotcheck
        exit $LASTEXITCODE
    }
    default {
        Write-Host "Usage: .\make.ps1 <up|down|test|lint|smoke-algos|schema-test|ingest-xz|normal-xz|takeover-xz|detectors-xz|cache-mail-xz|cache-github-xz|cache-inventory-xz|llm-test|reader-spotcheck>"
    }
}
