# Windows fallback for the Makefile. Usage: .\make.ps1 <target>   (targets: up, down, test, lint)
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "test", "lint", "smoke-algos", "schema-test", "ingest-xz", "normal-xz", "takeover-xz", "detectors-xz", "cache-mail-xz", "cache-github-xz", "cache-inventory-xz", "llm-test", "reader-spotcheck", "reader-testset", "reader-score", "reader-full", "pressure-vouch-xz", "quarterly-xz", "decision-xz", "slack-preview", "inbox", "replay", "hardening-fixture", "harden-xz", "demo", "ui", "synthetic-tallowdate", "tallowdate-run", "ecosystem-xz", "help")]
    [string]$Target = "help",

    [Parameter(Position = 1)]
    [string]$Case = "xz"
)

$ErrorActionPreference = "Stop"

switch ($Target) {
    "ecosystem-xz" {
        uv run python -m eval.ecosystem_xz
        exit $LASTEXITCODE
    }
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
    "reader-testset" {
        uv run python -m eval.reader_freeze
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run python -m eval.reader_testset
        exit $LASTEXITCODE
    }
    "reader-score" {
        uv run python -m eval.reader_score
        exit $LASTEXITCODE
    }
    "reader-full" {
        uv run python -m eval.reader_full_run
        exit $LASTEXITCODE
    }
    "pressure-vouch-xz" {
        uv run python -m eval.xz_pressure_vouch_status
        exit $LASTEXITCODE
    }
    "quarterly-xz" {
        uv run python -m eval.xz_quarterly_status
        exit $LASTEXITCODE
    }
    "decision-xz" {
        uv run python -m eval.xz_decision_status
        exit $LASTEXITCODE
    }
    "hardening-fixture" {
        uv run python -m core.hardening.simulate
        exit $LASTEXITCODE
    }
    "harden-xz" {
        uv run python -m core.hardening.xz
        exit $LASTEXITCODE
    }
    "slack-preview" {
        uv run python -m slack_app.render
        exit $LASTEXITCODE
    }
    "inbox" {
        Push-Location ui
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        npm run build
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        Pop-Location
        uv run python -m api.serve
        exit $LASTEXITCODE
    }
    "replay" {
        if ($Case -notmatch '^[a-z0-9_]+$') { Write-Host "bad CASE"; exit 2 }
        uv run python -m "eval.replay_$Case"
        exit $LASTEXITCODE
    }
    "demo" {
        uv run python -m eval.demo
        exit $LASTEXITCODE
    }
    "synthetic-tallowdate" {
        uv run python -m redteam.tallowdate
        exit $LASTEXITCODE
    }
    "tallowdate-run" {
        uv run python -m redteam.run_tallowdate
        exit $LASTEXITCODE
    }
    "ui" {
        Push-Location ui
        npm install
        if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        npm run dev
        $code = $LASTEXITCODE
        Pop-Location
        exit $code
    }
    default {
        Write-Host "Usage: .\make.ps1 <up|down|test|lint|smoke-algos|schema-test|ingest-xz|normal-xz|takeover-xz|detectors-xz|cache-mail-xz|cache-github-xz|cache-inventory-xz|llm-test|reader-spotcheck|reader-testset|reader-score|reader-full|pressure-vouch-xz|quarterly-xz|decision-xz|slack-preview|inbox|replay|hardening-fixture|harden-xz|demo|ui|synthetic-tallowdate|tallowdate-run>"
    }
}
