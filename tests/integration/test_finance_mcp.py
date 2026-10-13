"""pack-finance MCP server (spec §12.1): the two tools, and the server that registers them.

Hand-worked expectations on the Northbridge case at Sep 17:
  - approval_history for kestrel-metals: two earlier bank changes (bc-0001 May 2024, bc-0008 Jun
    2025), each portal / callback / 2 approvers / 2 approvals recorded; then the Sep 17 change:
    email / no callback / 1 approver / 0 approvals recorded (it is pending).
  - vendor_change_path: the latest kestrel-metals bank change is the Sep 17 one, and Bypass says
    it differs on channel, callback and approvers.
"""

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest

from eval import northbridge_case as nc
from packs.finance import mapping, parse, tools

SERVER = Path(__file__).resolve().parents[2] / "mcp_servers" / "pack-finance" / "server.py"


@pytest.fixture
def org(client):
    org = "nb" + uuid.uuid4().hex[:8]
    parsed = parse.parse_records(nc.load_dataset(), parse.default_salt())
    mapping.load(client, f"org_{org}", parsed, nc.T_CASE, org)
    yield org
    client.drop(f"org_{org}")


def test_approval_history_lists_the_earlier_changes_and_the_pending_one(client, org):
    h = tools.approval_history(client, org, "kestrel-metals", T=nc.T_CASE)
    got = [
        (
            c["action_ref"],
            c["channel"],
            c["callback"],
            c["approvers_required"],
            c["approvals_recorded"],
        )
        for c in h["changes"]
    ]
    assert got == [
        ("northbridge:erp:bc-0001", "portal", True, 2, 2),
        ("northbridge:erp:bc-0008", "portal", True, 2, 2),
        ("northbridge:erp:bc-k01", "email", False, 1, 0),
    ]
    assert h["T_defaulted"] is False


def test_vendor_change_path_reports_the_bypass(client, org):
    r = tools.vendor_change_path(client, org, "kestrel-metals", "bank_change", T=nc.T_CASE)
    assert r["found"] is True
    assert r["action_ref"] == "northbridge:erp:bc-k01"
    assert r["path"] == {"channel": "email", "callback": False, "approvers": 1}
    assert r["versus_normal"]["status"] == "FIRED"


def test_default_t_is_the_newest_action(client, org):
    r = tools.vendor_change_path(client, org, "kestrel-metals")
    assert r["T_defaulted"] is True
    assert r["T"] == parse.to_epoch("2025-09-17T10:00:00Z")


def test_unknown_vendor_is_a_result_not_an_error(client, org):
    r = tools.vendor_change_path(client, org, "no-such-vendor", T=nc.T_CASE)
    assert r["found"] is False


def test_the_tools_are_read_only(client, org):
    def fingerprint():
        n = client.query(f"org_{org}", "MATCH (n) RETURN count(n)", timeout_ms=30_000)
        e = client.query(f"org_{org}", "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000)
        return n.result_set[0][0], e.result_set[0][0]

    before = fingerprint()
    tools.approval_history(client, org, "kestrel-metals")
    tools.vendor_change_path(client, org, "kestrel-metals")
    assert fingerprint() == before


def test_the_server_registers_exactly_the_two_spec_tools():
    spec = importlib.util.spec_from_file_location("pack_finance_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    listed = asyncio.run(mod.server.list_tools())
    names = sorted(t.name for t in getattr(listed, "tools", listed))
    assert names == ["approval_history", "vendor_change_path"]
