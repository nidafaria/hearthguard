"""verify-packs (docs/HEARTHGUARD.md §4.2): the finance company runs with the OSS pack removed.

Run: uv run python -m eval.verify_packs
Checks, in order:
  1. static   core/ imports nothing from packs/, and packs/finance imports nothing from packs.oss.
  2. removal  copy core/, config/, packs/finance/, the case script and its data into a temp
              directory that has NO packs/oss, and run the Northbridge case there as a child
              process. Any import of the OSS pack would fail with ModuleNotFoundError.
  3. same     run the same case here, with the OSS pack present, and compare the two results.
              They must be equal: the OSS pack must not change what the finance company computes.
Both runs use scratch org ids and drop their graphs. Writes eval/results/finance_verify_packs.json
and exits 1 if any check fails.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from core.graph.client import FalkorClient
from eval import northbridge_case

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "eval" / "results" / "finance_verify_packs.json"
COPY = ("core", "config")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def imports_of(root: Path, prefix: str) -> list[str]:
    """Every import of `prefix` (a module or package) in the .py files under `root`: file:line."""
    hits = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(n == prefix or n.startswith(prefix + ".") for n in names):
                hits.append(f"{path.relative_to(root)}:{node.lineno}")
    return hits


def run_without_oss(org: str, out_file: Path) -> dict:
    """Run the case in a temp tree with no packs/oss. Returns {ok, stderr_tail, result}."""
    with tempfile.TemporaryDirectory(prefix="hg_verify_packs_") as tmp:
        tmp_root = Path(tmp)
        for name in COPY:
            shutil.copytree(ROOT / name, tmp_root / name, ignore=IGNORE)
        shutil.copytree(ROOT / "packs" / "finance", tmp_root / "packs" / "finance", ignore=IGNORE)
        (tmp_root / "eval").mkdir()
        shutil.copy(
            ROOT / "eval" / "northbridge_case.py", tmp_root / "eval" / "northbridge_case.py"
        )
        (tmp_root / "data" / "synthetic").mkdir(parents=True)
        shutil.copy(northbridge_case.DATA, tmp_root / "data" / "synthetic" / "northbridge.json")
        assert not (tmp_root / "packs" / "oss").exists()
        proc = subprocess.run(
            [sys.executable, "-m", "eval.northbridge_case", "--org", org, "--out", str(out_file)],
            cwd=tmp_root,
            env={**os.environ, "PYTHONPATH": str(tmp_root)},
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0 and out_file.exists()
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr.strip().splitlines()[-5:],
            "oss_pack_present_in_tree": (tmp_root / "packs" / "oss").exists(),
        }


def main() -> int:
    checks: dict = {}
    core_hits = imports_of(ROOT / "core", "packs")
    fin_hits = imports_of(ROOT / "packs" / "finance", "packs.oss")
    checks["static"] = {
        "core_imports_of_packs": core_hits,
        "finance_imports_of_packs_oss": fin_hits,
        "ok": not core_hits and not fin_hits,
    }

    tag = uuid.uuid4().hex[:8]
    client = FalkorClient()
    with tempfile.TemporaryDirectory(prefix="hg_verify_out_") as outdir:
        without_file = Path(outdir) / "without_oss.json"
        removal = run_without_oss(f"vp{tag}a", without_file)
        checks["removal"] = removal
        client.drop(f"org_vp{tag}a")
        with_result = northbridge_case.run(client, f"vp{tag}b")
        client.drop(f"org_vp{tag}b")
        same = False
        if removal["ok"]:
            without_result = json.loads(without_file.read_text(encoding="utf-8"))
            same = without_result == json.loads(json.dumps(with_result))
        checks["same_result"] = {"ok": same}
        checks["moves_without_oss"] = (
            {k: v["status"] for k, v in without_result["moves"].items()} if removal["ok"] else None
        )

    passed = all(c["ok"] for c in checks.values() if isinstance(c, dict) and "ok" in c)
    out = {"spec": "docs/HEARTHGUARD.md §4.2", "passed": passed, "checks": checks}
    RESULT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
