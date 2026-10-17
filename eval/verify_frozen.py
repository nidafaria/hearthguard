"""`make verify-frozen` (spec §10.1): does docs/FREEZE.md still match its recorded hash?

Run: uv run python -m eval.verify_frozen

Reads docs/FREEZE.md and docs/FREEZE.sha256 and writes nothing in docs/. Exit 0 only if the hash
matches. It also reports the status line of the file: a matching hash on a file that still says
DRAFT is reported as DRAFT, not as frozen. Line endings are not normalised, so a file that git
checked out with different line endings fails here and says so.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "docs" / "FREEZE.md"
HASH_FILE = ROOT / "docs" / "FREEZE.sha256"
RESULT = ROOT / "eval" / "results" / "verify_frozen.json"


def check(freeze: Path = FREEZE, hash_file: Path = HASH_FILE) -> dict:
    recorded = hash_file.read_text(encoding="utf-8").split()[0].lower()
    actual = hashlib.sha256(freeze.read_bytes()).hexdigest()
    status_line = next(
        (ln for ln in freeze.read_text(encoding="utf-8").splitlines() if ln.startswith("Status:")),
        "Status: (no status line)",
    )
    return {
        "file": freeze.name,
        "recorded_sha256": recorded,
        "actual_sha256": actual,
        "hash_matches": recorded == actual,
        "status_line": status_line,
        "frozen": recorded == actual and "DRAFT" not in status_line.upper(),
    }


def main() -> int:
    out = check()
    RESULT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    if not out["hash_matches"]:
        print("FAIL: docs/FREEZE.md does not match docs/FREEZE.sha256")
        return 1
    if not out["frozen"]:
        print("hash matches, but the file still says DRAFT: not frozen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
