"""MCP tool modules (spec §12.1): read-only by construction, no LLM, hashed ids only. No database.

Hand-worked expectations:
  - every Cypher constant in the two tool modules passes the repo's write-keyword guard and carries
    a LIMIT.
  - a raw identifier is hashed; a 64-hex value is taken to be a hid already and is not re-hashed.
  - neither tool module imports an LLM client or the Slack/Liaison send path.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from core.graph.hashing import identifier_hash
from core.graph.ro_guard import check_read_only

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "mcp_servers" / "hearthguard-core" / "tools.py"
OSS = ROOT / "mcp_servers" / "pack-oss" / "tools.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load(CORE, "mcp_unit_core")
oss = _load(OSS, "mcp_unit_oss")


def _queries(mod):
    return {k: v for k, v in vars(mod).items() if k.endswith("_QUERY") and isinstance(v, str)}


@pytest.mark.parametrize("mod", [core, oss], ids=["core", "oss"])
def test_every_query_is_read_only_and_limited(mod):
    qs = _queries(mod)
    assert qs
    for name, cypher in qs.items():
        check_read_only(cypher)
        assert re.search(r"\bLIMIT\b", cypher), name


@pytest.mark.parametrize("path", [CORE, OSS], ids=["core", "oss"])
def test_no_llm_and_no_send_path(path):
    src = path.read_text(encoding="utf-8")
    for banned in ("core.llm", "anthropic", "slack_app", "core.agents.liaison", "send_message"):
        assert banned not in src, banned


def test_raw_identifiers_are_hashed_and_hids_are_not():
    hid = identifier_hash("someone@example.invalid")
    assert core.to_hid("someone@example.invalid") == hid
    assert core.to_hid(hid) == hid


def test_default_t_refuses_an_empty_graph_message():
    class Empty:
        def query(self, *a, **k):
            raise AssertionError("should not be reached")

    with pytest.raises(ValueError):
        core.simulate_hardening(Empty(), "x", "not_a_step")
