# Judge guide

A path through the project. The whole path is meant to take about half an hour. That is an estimate, not a timed run.

Steps 1 to 9 need no database and no key. Steps 10 to 13 are optional. They need Docker, and a local `.env` with `HEARTHGUARD_HASH_SALT`.

Each step says what to run or read, the output to expect, and the file it comes from. Windows commands use `.\make.ps1`. On Linux or macOS, use `make` with the same target name, once `make` is installed.

## 1. Read what the project claims

Open `README.md`.

- **Expect:** the README says the project is provisional and not complete. It says the xz backdoor is **not** detected in this build.
- **From:** `README.md`

## 2. Check that the rules have not changed since the hash was recorded

Run:

```powershell
(Get-FileHash docs/FREEZE.md -Algorithm SHA256).Hash
Get-Content docs/FREEZE.sha256
```

- **Expect:** both lines show the same hash. The comparison ignores case.
- **From:** `docs/FREEZE.md` and `docs/FREEZE.sha256`. `docs/FREEZE.md` is still a draft (`eval/results/completion_full.md`, row 77).

## 3. Set up the Python environment

```powershell
uv sync
```

- **Expect:** uv installs the packages and finishes without an error.
- **From:** `pyproject.toml`, `uv.lock`

## 4. Run the no-key demo

```powershell
.\make.ps1 demo
```

- **Expect:** the command finishes without an error. The output starts with `# xz replay (provisional)`. It has one table row per quarter-end, from 2021-Q4 to 2024-Q1 (`eval/results/decision_status.json`). Each row ends with `HOLD`. The footer says "NOT COMPUTED means the input does not exist in the public data; it is not a clean result."
- **From:** `eval/demo.py`, which prints `eval/results/xz_replay.md`. The table is built from `eval/results/xz_normal.json`, `eval/results/xz_quarterly_status.json`, `eval/results/pressure_vouch_status.json` and `eval/results/decision_status.json`.

## 5. Check that the replay rebuilds from saved files

```powershell
.\make.ps1 replay
git status --short eval/results
```

- **Expect:** the replay finishes without an error. `git status` lists no changed files under `eval/results`, so the output is the same as the committed output.
- **From:** `Makefile` (target `replay`), `eval/replay_xz.py`

## 6. Read the decision for every quarter

```powershell
.\make.ps1 decision-xz
```

- **Expect:** ten lines in this form: `2021-Q4 HOLD move unknown: RUSH, BYPASS`, down to `2024-Q1` (`eval/results/decision_status.json`).
- **Side effect:** this command rewrites the tracked file `eval/results/decision_status.json`. Only its `generated_at_utc` line changes, so `git status` shows one modified file afterwards. To restore the committed copy, run `git checkout -- eval/results/decision_status.json`.
- **From:** `eval/results/decision_status.json`, field `decision` and `detail.reason`. The rule is in `core/policy/decision.py` and `docs/decisions/0002-decision-unknowns.md`.

## 7. See why it is HOLD

Open `eval/results/decision_status.json` and look at the first quarter's `reasons`.

- **RUSH:** `no Privilege of kind 'release' in org_xz, so no grant data` (`eval/results/decision_status.json`)
- **BYPASS:** `single shared Path node, no variation to compare` (`eval/results/decision_status.json`)
- **PRESSURE:** `0 PRESSURE/URGENCY claims from 0 low-history actors in the last 120 days; need 3 claims from 2 actors` (`eval/results/decision_status.json`)

A HOLD here does not mean the xz backdoor was found. It means two of the four moves could not be computed. See "What this does not show" below.

## 8. Check the grant search

Open `eval/results/xz_grant_search.json` and find `grant_records_found`.

- **Expect:** `"grant_records_found": 0` and `"status": "NOT COMPUTED"` (`eval/results/xz_grant_search.json`). The `note` field explains one commit-message match that was read and found not to be a grant.
- **From:** `eval/results/xz_grant_search.json`

## 9. Check how much of the Reader ran

Open `eval/results/reader_full_progress.json`.

- **Expect:** `"total": 240`, `"done": 94`, `"remaining": 146`, and `"stopped_because"` names the daily token limit of 200000 tokens (`eval/results/reader_full_progress.json`).
- **From:** `eval/results/reader_full_progress.json`. The held-back messages are in `eval/results/reader_testset.json`.

Then open `eval/results/pressure_vouch_status.json` and find `coverage`. Expect `"read_so_far": 90` and `"recorded_but_not_read": 4`. Pressure and Vouch say NOT_FIRED only for the messages the Reader read.

## 10. Run the decision-policy tests (optional)

```powershell
uv run pytest tests/unit/test_policy.py tests/unit/test_xz_decision_status.py -q
```

- **Expect:** all tests pass.
- **From:** `tests/unit/test_policy.py`, `tests/unit/test_xz_decision_status.py`

## 11. Start the graph database (optional, needs Docker)

```powershell
.\make.ps1 up
```

- **Expect:** the FalkorDB container is running. The image is pinned to `falkordb/falkordb:6.0.2` (`docker-compose.yml`).
- **From:** `docker-compose.yml`. If a port is already in use, set `FALKORDB_PORT` (client, default 6379, `core/graph/client.py`) or `FALKORDB_UI_PORT` (browser UI, default 3000) in `.env`.

## 12. Re-check the FalkorDB procedures the product depends on (optional, needs step 11)

```powershell
.\make.ps1 smoke-algos
```

- **Expect:** all tests pass. One test is an expected xfail.
- **From:** `tests/integration/test_smoke_algos.py`

## 13. Run the full test suite (optional, needs step 11 and a `.env`)

```powershell
.\make.ps1 test
```

- **Expect:** `467 passed, 1 xfailed`, the same as the recorded run (`eval/results/final_tests.json`, recorded at commit 796ac40).
- **From:** `eval/results/final_tests.json`. The tests need `HEARTHGUARD_HASH_SALT` in `.env`. Without it, several tests fail with `MissingSaltError`. That is a setup problem, not a code problem.

## Optional: open the read-only page (needs Node)

```powershell
.\make.ps1 ui
```

Open http://localhost:5173. The page shows the same replay table, and marks missing inputs as NOT COMPUTED.

- **From:** `ui/vite.config.ts`, `ui/src/App.tsx`

## Next

Read `docs/decisions/index.md`. Every decision there is still open. Read `docs/AI_USE.md` for what the AI assistants did.

---

## What this does not show

- **It does not detect the xz backdoor.** The xz backdoor was in the release tarballs, not in the git history. The replay only reads git and the mailing list (`eval/results/xz_normal.json`, notes).
- **It does not show a takeover cost.** No grant record was found, so takeover cost, guardians, Rush, Bypass and Lone keeper are NOT COMPUTED (`eval/results/xz_grant_search.json`, `eval/results/decision_status.json`).
- **It does not show a result from all the messages.** The Reader read 94 of 240 messages. The free model allowance stopped it. The rest are unread (`eval/results/reader_full_progress.json`).
- **It does not measure the Reader.** There are no human labels. Precision and recall are NOT COMPUTED. The Haiku labels are an AI second opinion, not ground truth (`docs/AI_USE.md`).
- **NOT_FIRED does not mean clean.** It means the Reader found no claim in the messages it read (`eval/results/pressure_vouch_status.json`).
- **It does not show a working hardening simulator, Slack loop, MCP server, finance pack or census.** These are NOT STARTED: 20 DONE, 25 PARTIAL and 86 NOT STARTED, of 131 rows (`eval/results/completion_full.md`).
- **It does not show the Act II case.** Act II, `tallowdate`, is synthetic and not built yet (`docs/HEARTHGUARD.md` §3.5).
- **The rules are not frozen.** `docs/FREEZE.md` is a draft. Its hash matches the recorded hash, but the freeze has not been signed (`eval/results/completion_full.md`, row 77).
- **It is not checked against real maintainers.** The spec's MAINTAINERS and CODEOWNERS check is not built (`docs/HEARTHGUARD.md` §10.2).
- **The demo video and blog are not finished.** See `docs/submission_checklist.md`.
