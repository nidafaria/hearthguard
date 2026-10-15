# Fresh clone report

What a judge gets: a clone of the repo with no `.env`, no `data/raw/`, no caches and no `node_modules`. Each run below used a new folder, cloned from the local repo's committed HEAD. Nothing was copied from the working tree.

Script: `eval/fresh_clone_test.ps1`. Run it with `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 -Dest <folder>`. Add `-WithTests` to also run the full `make test`.

## Runs

| Run | Clone path | Commit | Branch | Notes |
|---|---|---|---|---|
| 1 (before fixes) | `scratchpad\clone1` (scratchpad of the session) | `00b09ea4816ce72ede59e9514da4782f2952cd1f` | main | Failures recorded here. Nothing fixed yet. |
| 2 (after fixes) | `scratchpad\clone2` (scratchpad of the session) | see "Run 2" below | agent/fresh-clone | Same commands, re-run from the script. |

## Git-ignored files absent from the clone

These exist in the source repo's working tree and are absent in both clones:

- `.env`
- `data/raw/`, `data/derived/`, `data/llm_cache/` (listed in `.gitignore`)
- `.venv/`, `.pytest_cache/`, `.ruff_cache/`
- `__pycache__/` directories
- `ui/node_modules/`

The demo inputs are tracked and present: `eval/results/xz_normal.json`, `eval/results/xz_quarterly_status.json`, `eval/results/pressure_vouch_status.json`, `eval/results/decision_status.json`, and the rest of `eval/results/` (37 tracked files).

## Run 1: README commands in the fresh clone (before fixes)

| Command (as run) | Exit | First error line |
|---|---|---|
| `uv sync` | 0 | |
| `.\make.ps1 demo` | 0 | |
| `.\make.ps1 demo` under the Restricted execution policy | 1 | `running scripts is disabled on this system` |
| `python -m eval.demo` with sockets blocked | 0 | |
| `.\make.ps1 lint` | 0 | |
| `.\make.ps1 replay xz` | 0 | |
| `.\make.ps1 decision-xz` | 0 (modifies a tracked file, see F3) | |
| `npm install` in `ui/` | 0 | |
| `npm run build` in `ui/` | 0 | |
| `uv run pytest tests/unit/test_policy.py tests/unit/test_xz_decision_status.py -q` (judge guide step 10) | 0 | 106 passed |
| `uv run pytest tests/unit tests/injection -q` (no FalkorDB, no `.env`) | 1 | `redis.exceptions.AuthenticationError` and `MissingSaltError` (20 failed, 366 passed, 11 skipped, 6 errors) |
| `.\make.ps1 test` (full suite, no FalkorDB, no `.env`) | 1 | `ConnectionError` from the integration tests. Summary: 25 failed, 388 passed, 12 skipped, 1 xfailed, 126 errors |
| `npm run dev` (`.\make.ps1 ui`), HTTP check | n/a (server kept running for the check) | `/results/decision_status.json` gives 200, a missing file gives 404, `/` gives 200 |

Not run: `make.ps1 up`, `smoke-algos`, `schema-test`, `ingest-xz`, `llm-test`, `reader-*`, `pressure-vouch-xz`, `quarterly-xz`, `cache-*`, `synthetic-tallowdate`, `tallowdate-run`, `harden-xz`, `inbox`. They need FalkorDB, a Docker daemon, a `GROQ_API_KEY`, or network access to GitHub and the mail archive. The judge guide marks these optional. Running them here would spend quota or change cached data.

## Failures found

### F1. `make test` cannot pass in a clean clone, and the README said it needed only uv

- Step: README "Commands", row `test`. Judge guide step 13 says it needs FalkorDB and a `.env`.
- Failure: 25 failed, 388 passed, 12 skipped, 1 xfailed, 126 errors, exit 1. The integration tests fail with `ConnectionError` because no FalkorDB is running. The graph and hashing tests fail with `AuthenticationError` or `MissingSaltError`.
- Fix: README row now says FalkorDB and `.env` are needed for the full suite. The demo does not need them.
- Not fixed in code. The tests need a real FalkorDB by design (CLAUDE.md), so they cannot pass with no services. Starting `make up` and adding `HEARTHGUARD_HASH_SALT` to a `.env` is the way to run them.
- File changed: `README.md`.

### F2. `.\make.ps1` is blocked by the default Windows execution policy

- Step: the README Windows route, `.\make.ps1 demo`.
- Failure: with the Restricted policy (the Windows client default), the command exits 1 with `running scripts is disabled on this system`. The Bypass form exits 0. This machine had the policy set to Bypass for the process, so the failure does not show on the author's machine.
- Fix: the README shows `powershell -ExecutionPolicy Bypass -File .\make.ps1 demo` and explains the difference. It also says `uv` must be on the PATH. The judge guide preamble gives the same form.
- Files changed: `README.md`, `docs/judge_guide.md`.

### F3. `decision-xz` rewrites a tracked file

- Step: judge guide step 6, `.\make.ps1 decision-xz`.
- Failure: the command changes `generated_at_utc` in `eval/results/decision_status.json`. The rest of the file is byte-identical. The judge's `git status` is then not clean, which breaks the expectation in step 5.
- Fix: the judge guide says so and gives `git checkout -- eval/results/decision_status.json` to restore the file.
- Not fixed in code. Changing the script or the file would change a committed result file.
- File changed: `docs/judge_guide.md`.

### F4. `.env.example` named a variable that no code reads

- `LLM_API_KEY` was in `.env.example`. The code reads `GROQ_API_KEY` only (`core/llm/client.py`). A judge who filled in the example would get no key for the Reader.
- Fix: the unused line was removed.
- File changed: `.env.example`.

## Demo result

- Exit code 0 in both runs.
- Needs a key: no. The demo reads `eval/results/*.json` and `eval/results/xz_replay.md`.
- Needs FalkorDB: no.
- Needs network: no. Run 1 used a Python wrapper that replaces `socket.socket`, `socket.create_connection` and `socket.getaddrinfo` with functions that raise. Exit 0, and the output bytes matched the normal run (2196 bytes, `fc /b` reported no differences).
- Output: the replay table, `# xz replay (provisional)`, ten quarter rows from 2021-Q4 to 2024-Q1, each with `HOLD`, and the footer about NOT COMPUTED.

## Limits of this test

- Only Windows was tested. `make` is not installed here, so the Linux and macOS `make` route was not run.
- Docker was not run, so `make up` is untested.
- The UI was checked over HTTP only. No browser was used.
- The live Groq calls were not run (no key, and they spend quota).
- On this machine, something on `localhost:6379` answered with `Authentication required`. A judge's FalkorDB could clash with a port already in use. The judge guide already covers changing `FALKORDB_PORT`.

## Run 2: after fixes

Clone: `scratchpad\clone2`. Commit `8a1f9e73a7b032ff6d155ef82271b29ee934eb26` (agent/fresh-clone). Command: `eval\fresh_clone_test.ps1 -Dest <clone2>`.

| Step | Run 1 (clone1, `00b09ea`) | Run 2 (clone2, `8a1f9e7`) |
|---|---|---|
| `uv sync` | 0 | 0 |
| `make.ps1 demo` | 0 | 0 |
| `make.ps1 demo`, sockets blocked | 0 | 0 |
| `make.ps1 lint` | 0 | 0 |
| `make.ps1 replay xz` | 0 | 0 |
| `make.ps1 decision-xz` | 0 | 0 |
| `npm install` / `npm run build` | 0 / 0 | 0 / 0 |
| unit + injection tests, no services | 1: 20 failed, 366 passed, 11 skipped, 6 errors | 1: 21 failed, 365 passed, 11 skipped, 6 errors |

**Demo output:** identical in both runs. Run 2 demo SHA256 (`03_demo.log`) is `AF14066480E2260AB1488A8CEA06305F2052A8D24C126C8C0B28B9A6BB571E39`. The no-network run wrote the same bytes.

**Test sets:** the failing-test names match between runs except for one test.

- Differing test: `tests/unit/test_slack_render.py::test_preview_file_matches_a_fresh_render`.
  - Run 1: passed.
  - Run 2: failed. `assert ... == ...`, differing item `decision_status_generated_at_utc`: committed `2026-10-12T12:53:46Z`, fresh render `2026-10-12T14:06:21Z`.

**Verdict: a real state difference, not flakiness.** The code is the same. The difference is the order of steps in the run:

- In run 1, I restored `eval/results/decision_status.json` with `git checkout` before the unit tests ran, so the test saw the committed timestamp.
- In run 2, the script ran `decision-xz` first, which rewrote that timestamp (F3). The test then compared the committed preview with a fresh render that had a different timestamp.

The test is deterministic given that state. Fixing it means changing either the script's step order (run unit tests before `decision-xz`) or the test's comparison of timestamps. I did not change either, and I did not rerun the script after this comparison.

The final `git status` in run 2 shows ` M eval/results/decision_status.json`, which is the F3 side effect.

## Run 3 and run 4: after moving the unit tests before decision-xz

The script now runs the unit tests before `decision-xz` (commit `af78390`). Both runs used new clones, `scratchpad\clone3` and `scratchpad\clone4`, on the same commit. They ran in parallel.

| Check | Run 3 (clone3) | Run 4 (clone4) |
|---|---|---|
| Clone, `uv sync`, demo, demo with sockets blocked, lint, replay, `npm install`, `npm run build`, `decision-xz` | all 0 | all 0 |
| Unit + injection tests, no services | exit 1: 20 failed, 366 passed, 11 skipped, 6 errors | exit 1: 20 failed, 366 passed, 11 skipped, 6 errors |
| Failing test names (22 lines) | same set | same set |
| Demo log | SHA256 `AF14066480E2260AB1488A8CEA06305F2052A8D24C126C8C0B28B9A6BB571E39` | same SHA256, identical file |
| `git status` after run | ` M eval/results/decision_status.json` (F3) | same |

**Result:** the unit-test counts match (20 failed, 366 passed, 11 skipped, 6 errors). The demo output is byte-identical. The only difference is run time (131.42 s and 130.24 s).

`test_preview_file_matches_a_fresh_render` now passes in both runs. The unit tests run before `decision-xz` now, so the committed timestamp is intact when they run. The unit-test failures that remain are the expected ones: no FalkorDB at `localhost:6379`, and no `HEARTHGUARD_HASH_SALT`.

## Run 5: block B, after skipping git-ignored data and salt

Commit: the last commit on agent/block-b before this report was written (see `git log`). Command: `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 -WithTests`. Logs in the scratchpad folder, not committed.

Changes in this run, all in tests (no detector or policy logic changed):

- `tests/integration/test_ecosystem_xz.py` and `tests/integration/test_xz_ingest.py` skip the whole module, with a reason, when the git-ignored cache they read is absent. The ecosystem module no longer fetches from inside a test. Before this, `test_ecosystem_xz` tried to fetch and hung for minutes on the network.
- `tests/unit/conftest.py` gains `needs_salt`, a skip with a reason when `HEARTHGUARD_HASH_SALT` is not set (`.env` is git-ignored). It is applied to the mail-cache, raw-inventory, git-ingest, tallowdate-load and connect integration tests.

Results (clone of agent/block-b at the final commit):

| Step | Exit | Result |
|---|---|---|
| clone, `uv sync`, README demo, replay, decision-xz, `npm install`, `npm run build` | 0 | as before |
| `make demo` twice | 0 | byte-identical (SHA256 recorded in the log) |
| `unit tests, no services` | 1 | 14 failed, 380 passed, 17 skipped, 6 errors. Every failure is `redis.exceptions.AuthenticationError`: the clone has no `.env`, so `FALKORDB_PORT` defaults to 6379 and reaches another Redis that requires a password, or no FalkorDB at all |
| `test full` | 1 | 17 failed, 401 passed, 40 skipped, 1 xfailed, 120 errors. 149 of the failure lines are the same FalkorDB `AuthenticationError`. One failure is `test_xz_decision_status` and one is `test_preview_file_matches_a_fresh_render`: both compare against `eval/results/decision_status.json`, which the clone's `decision-xz` step rewrites (the F3 note above). Only `generated_at_utc` differs |
| `lint` | 1 | 44 errors, repo-wide. Not from this block's code: `eval/video_check.py` (39), `eval/blog_check.py` (3). The rest are `eval/completion_full.py` (the loader hook, E402 and I001, as specified in the brief) and the long evidence strings in `eval/completion_updates/block_b.py` (E501 is exempted there) |

What a judge sees in a clean clone after this run: no git-ignored data is needed by any test that passes or fails for a data reason. A full run still needs FalkorDB (`make up`) and `.env` with the salt, as README "Commands" says. Lint still fails on the files named above.

Not fixed here: the `decision-xz` step rewrites a tracked file (F3). Not fixed here: the FalkorDB requirement, which is a service and not git-ignored data.

## Run 6: after the preview-stamp fix and the README first step

Commit: 776f07b. Command: `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 -WithTests`. Logs in the scratchpad folder, not committed.

- `test_preview_file_matches_a_fresh_render` now passes in the clone. decision-xz still rewrites `generated_at_utc` in `decision_status.json`, and the test checks that stamp as a timestamp and the rest of the content without it. The clone's `test_xz_decision_status` passed in both steps.
- Every remaining error line in both test steps is `redis.exceptions.AuthenticationError`. The clone has no `.env` and no FalkorDB, so the default port reaches an auth-protected Redis or nothing.

| Step | Exit | Result |
|---|---|---|
| `unit tests, no services` | 1 | 14 failed, 380 passed, 17 skipped, 6 errors. All FalkorDB `AuthenticationError` |
| `test full` | 1 | 16 failed, 402 passed, 40 skipped, 1 xfailed, 120 errors. All FalkorDB `AuthenticationError` |
| `lint` | 1 | 44 repo-wide errors, unchanged cause (see run 5) |
| `decision-xz`, `ui build`, demo, replay | 0 | as before |

What still stops a clean clone from going green: a FalkorDB database (`make up`) and a `.env` with `HEARTHGUARD_HASH_SALT`, both listed in the README's first step. Lint is unchanged.

## Run 7: clean clone of main at f26c75e

Command: `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 -Dest <new folder>` (no `-WithTests`). New clone of main, nothing copied from the working tree. `.env`, `data/raw`, `data/derived`, `data/llm_cache`, `.venv` and `ui/node_modules` were all absent in the clone. No setup defect was found, so no setup file was changed in this run. Results are unchanged.

| Command | Exit | First error line |
|---|---|---|
| `git clone --branch main` | 0 | |
| `uv sync` | 0 | |
| `make.ps1 demo` | 0 | |
| demo with sockets blocked | 0 | |
| `make.ps1 lint` | 0 | |
| `make.ps1 replay xz` | 0 | |
| `make.ps1 decision-xz` | 0 | (rewrites `generated_at_utc` in `eval/results/decision_status.json`, F3) |
| `npm install` in `ui/` | 0 | |
| `npm run build` in `ui/` | 0 | |
| `uv run pytest tests/unit tests/injection -q` | 1 | `redis.exceptions.AuthenticationError: Authentication required.` (15 failed, 601 passed, 17 skipped, 6 errors; one failure is `MissingSaltError`) |

The one failing command needs a FalkorDB and a `.env` with `HEARTHGUARD_HASH_SALT`, which a clone does not have by design (README first step). Demo log SHA256: `111B4C02F7CA3C1E9FDC6546E2F83D460001393D1F738D14D026B100E809811F`.

The full `make test` was run in the author's working tree, with FalkorDB and `.env`: 959 passed, 0 failed, 1 xfailed.
