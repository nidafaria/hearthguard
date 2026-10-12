# Fresh-clone test: what a judge gets. Clones the repo's committed HEAD into a new folder,
# then runs the README commands there. Nothing is copied from the working tree, so no .env,
# data/raw/, data/derived/, data/llm_cache/ or node_modules come along.
#
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 [-Source <repo>] [-Dest <folder>] [-WithTests]
#
# Writes one log per step to <Dest>\..\fresh_clone_logs\<run>\ and prints a table of exit codes.
# The demo output is hashed so two runs can be compared. Never prints .env values.

param(
    [string]$Source = (git rev-parse --show-toplevel),
    [string]$Dest = (Join-Path $env:TEMP ("hearthguard_fresh_" + (Get-Date -Format "yyyyMMdd_HHmmss"))),
    [switch]$WithTests
)

$ErrorActionPreference = "Continue"
$Branch = (git -C $Source rev-parse --abbrev-ref HEAD).Trim()
$Commit = (git -C $Source rev-parse HEAD).Trim()
$LogDir = Join-Path (Split-Path $Dest -Parent) ((Split-Path $Dest -Leaf) + "_logs")
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$results = @()

function Invoke-Step {
    param([string]$Name, [string]$WorkDir, [string]$CommandLine)
    $log = Join-Path $LogDir ($Name + ".log")
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "$CommandLine > `"$log`" 2>&1" `
        -WorkingDirectory $WorkDir -NoNewWindow -Wait -PassThru
    $code = $p.ExitCode
    $first = ""
    if ($code -ne 0 -and (Test-Path $log)) {
        $first = (Get-Content $log -Encoding UTF8 | Where-Object { $_ -match "error|Error|ERROR|Traceback|failed|not recognized" } | Select-Object -First 1)
    }
    $script:results += [pscustomobject]@{ Step = $Name; Exit = $code; FirstError = $first }
    return $code
}

# Step 1: true fresh clone of the committed HEAD.
$cloneCode = Invoke-Step -Name "01_clone" -WorkDir (Split-Path $Dest -Parent) -CommandLine "git clone --branch $Branch `"$Source`" `"$Dest`""
if ($cloneCode -ne 0) { $results | Format-Table -AutoSize | Out-String | Write-Host; exit 1 }

# Git-ignored paths that a judge will not have. Each should be absent.
$ignoredAbsent = @(".env", "data/raw", "data/derived", "data/llm_cache", ".venv", "ui/node_modules")
$absentReport = foreach ($p in $ignoredAbsent) {
    [pscustomobject]@{ Path = $p; Present = (Test-Path (Join-Path $Dest $p)) }
}

# Step 2: README setup, in order.
$null = Invoke-Step -Name "02_uv_sync" -WorkDir $Dest -CommandLine "uv sync"

# Step 3: demo from committed files. Needs no key, no FalkorDB, no network.
$demoCode = Invoke-Step -Name "03_demo" -WorkDir $Dest -CommandLine "powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 demo"
$demoHash = ""
if (Test-Path (Join-Path $LogDir "03_demo.log")) {
    $demoHash = (Get-FileHash (Join-Path $LogDir "03_demo.log") -Algorithm SHA256).Hash
}

# Same demo with sockets blocked in the Python process. Proves no network call is needed.
$noNet = @'
import os, runpy, socket, sys
sys.path.insert(0, os.getcwd())
def _blocked(*a, **k):
    raise RuntimeError("network blocked by fresh-clone test")
class _NoSocket(socket.socket):
    def __init__(self, *a, **k):
        raise RuntimeError("network blocked by fresh-clone test")
socket.socket = _NoSocket
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
runpy.run_module("eval.demo", run_name="__main__")
'@
$noNetPath = Join-Path $LogDir "nonet_demo.py"
Set-Content -Path $noNetPath -Value $noNet -Encoding utf8
$noNetCode = Invoke-Step -Name "03_demo_no_network" -WorkDir $Dest -CommandLine "uv run python `"$noNetPath`""

# Step 2 continued: the other no-key, no-database README commands.
$null = Invoke-Step -Name "02_lint" -WorkDir $Dest -CommandLine "powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 lint"
$null = Invoke-Step -Name "02_replay_xz" -WorkDir $Dest -CommandLine "powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 replay xz"
# Unit tests run before decision-xz, which rewrites a tracked file (see docs/fresh_clone_report.md).
$null = Invoke-Step -Name "02_unit_tests_no_services" -WorkDir $Dest -CommandLine "uv run pytest tests/unit tests/injection -q -p no:cacheprovider"
$null = Invoke-Step -Name "02_decision_xz" -WorkDir $Dest -CommandLine "powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 decision-xz"
$null = Invoke-Step -Name "02_ui_install" -WorkDir (Join-Path $Dest "ui") -CommandLine "npm install --no-audit --no-fund"
$null = Invoke-Step -Name "02_ui_build" -WorkDir (Join-Path $Dest "ui") -CommandLine "npm run build"

if ($WithTests) {
    $null = Invoke-Step -Name "02_test_full" -WorkDir $Dest -CommandLine "powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 test"
}

# Git state after the run. decision-xz is expected to modify one tracked file (see docs/judge_guide.md, step 6).
$gitStatus = (git -C $Dest status --short) -join "; "

# Summary.
"Clone: $Dest"
"Commit: $Commit ($Branch)"
"Logs: $LogDir"
""
"Git-ignored paths absent in the clone:"
$absentReport | Format-Table -AutoSize | Out-String | Write-Host
$results | Format-Table -AutoSize | Out-String | Write-Host
"Demo SHA256 (stdout log): $demoHash"
"git status after run: $gitStatus"
