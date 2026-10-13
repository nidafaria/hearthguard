"""Proof that the frozen code did not change while the red-team results were produced.

Every red-team, hardening, ablation and replay output carries provenance(): the git commit the
code ran at, whether the working tree was dirty, and the SHA-256 of the source of each detector,
policy and takeover function, next to the same function at the commit this branch started from
(the merge-base with main) and a `match` flag. The frozen docs and the thresholds file are hashed
the same way. A False `match` means a frozen function changed: the integration test fails on it.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, function) pairs: every detector, the conflict and decision policies, takeover cost,
# guardians and the pure helpers they call.
FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("core/detectors/rush.py", "rush"),
    ("core/detectors/rush.py", "decide"),
    ("core/detectors/rush.py", "percentile_cont"),
    ("core/detectors/bypass.py", "bypass"),
    ("core/detectors/bypass.py", "judge"),
    ("core/detectors/lone_keeper.py", "lone_keeper"),
    ("core/detectors/pressure.py", "pressure"),
    ("core/detectors/vouch.py", "vouch"),
    ("core/detectors/vouch.py", "components"),
    ("core/detectors/low_history.py", "is_low"),
    ("core/takeover/cost.py", "takeover_cost"),
    ("core/takeover/guardians.py", "guardians"),
    ("core/policy/decision.py", "decide"),
    ("core/policy/decision.py", "decide_with_unknowns"),
    ("core/policy/decision.py", "evidence_from_moves"),
    ("core/policy/conflict.py", "resolve"),
)
FILES: tuple[str, ...] = ("config/frozen.yaml", "docs/FREEZE.md", "docs/FREEZE.sha256")


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60
    )
    return out.stdout.strip()


def _git_bytes(*args: str) -> bytes:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True, timeout=60)
    return out.stdout


def _sha(text: str | bytes) -> str:
    b = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(b).hexdigest()


def _norm(b: bytes) -> bytes:
    return b.replace(bytes([13, 10]), bytes([10])).strip()


def function_source(text: str, name: str) -> str | None:
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


def base_commit() -> str:
    """The commit this branch started from: the merge-base with main."""
    try:
        return _git("merge-base", "HEAD", "main")
    except subprocess.CalledProcessError:
        return _git("rev-parse", "HEAD")


def provenance() -> dict:
    base = base_commit()
    funcs = []
    for path, name in FUNCTIONS:
        now = function_source((ROOT / path).read_text(encoding="utf-8"), name)
        try:
            then = function_source(
                _git_bytes("show", f"{base}:{path}")
                .decode("utf-8")
                .replace(chr(13) + chr(10), chr(10)),
                name,
            )
        except subprocess.CalledProcessError:
            then = None
        if now is None:
            # conflict.py may name its entry point differently; a missing name is reported
            funcs.append({"file": path, "function": name, "found": False})
            continue
        funcs.append(
            {
                "file": path,
                "function": name,
                "found": True,
                "sha256": _sha(now),
                "base_sha256": _sha(then) if then is not None else None,
                "match": then is not None and _sha(now) == _sha(then),
            }
        )
    files = []
    for path in FILES:
        now = (ROOT / path).read_bytes()
        try:
            then = _git_bytes("show", f"{base}:{path}")
        except subprocess.CalledProcessError:
            then = None
        files.append(
            {
                "file": path,
                "sha256": _sha(now),
                # compare with line endings and the trailing newline normalised (Windows checkout)
                "match": then is not None and _norm(now) == _norm(then),
            }
        )
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "base_commit": base,
        "working_tree_dirty": bool(_git("status", "--porcelain", "--", "core", "config", "docs")),
        "functions": funcs,
        "files": files,
        "frozen_unchanged": all(f["match"] for f in funcs if f.get("found"))
        and all(f["match"] for f in files),
    }
