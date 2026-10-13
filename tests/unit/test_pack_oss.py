"""The OSS pack (spec §4.2): privileges, normal path, claim vocabulary; core never imports packs."""

import ast
from pathlib import Path

from core.claims.reader import ClaimKind
from core.detectors.bypass import PACK_PROPERTIES
from packs.oss import pack

ROOT = Path(__file__).resolve().parents[2]


def test_privilege_kinds_are_the_four_in_the_spec():
    assert pack.PRIVILEGE_KINDS == ("merge", "release", "sign", "npm_publish")


def test_sensitive_flags():
    # Hand-worked: release, sign and npm_publish are the power to ship; merge is reviewed first.
    assert pack.SENSITIVE_PRIVILEGES == ("release", "sign", "npm_publish")
    assert {p.kind: p.sensitive for p in pack.PRIVILEGES}["merge"] is False


def test_normal_path_is_what_the_bypass_detector_compares():
    assert pack.NORMAL_PATH["properties"] == PACK_PROPERTIES["oss"]


def test_claim_vocabulary_is_the_reader_vocabulary():
    assert set(pack.CLAIM_VOCABULARY) == {k.value for k in ClaimKind if k is not ClaimKind.NONE}
    assert all(pack.CLAIM_VOCABULARY.values())


def packs_imports(root: Path) -> list[str]:
    """Every import of `packs` found in the .py files under `root`, as file:line."""
    offenders = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(n == "packs" or n.startswith("packs.") for n in names):
                offenders.append(f"{path.name}:{node.lineno}")
    return offenders


def test_core_imports_nothing_from_packs():
    assert packs_imports(ROOT / "core") == []


def test_the_scan_catches_a_bad_import(tmp_path):
    """Try to break the scan: both import forms must be flagged."""
    (tmp_path / "bad.py").write_text("from packs.oss import pack\nimport packs.oss\nimport os\n")
    assert packs_imports(tmp_path) == ["bad.py:1", "bad.py:2"]
