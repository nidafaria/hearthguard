# Windows fallback for the Makefile. Usage: .\make.ps1 <target>   (targets: up, down, test, lint)
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "test", "lint", "help")]
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
    default {
        Write-Host "Usage: .\make.ps1 <up|down|test|lint>"
    }
}
