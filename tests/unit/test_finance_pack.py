"""Finance pack, no database: definition, parsers, dataset, approval authority at a horizon.

Hand-worked expectations are written in each test.
"""

from pathlib import Path

import pytest

from core.claims.reader import ClaimKind
from core.detectors.bypass import FEWER_IS_BYPASS, PACK_PROPERTIES
from core.memory import who_saw
from eval.verify_packs import imports_of
from packs.finance import mapping, pack, parse, synthetic

ROOT = Path(__file__).resolve().parents[2]
SALT = b"unit-test-salt"


def test_privileges_are_the_three_in_the_spec():
    assert pack.PRIVILEGE_KINDS == ("vendor_edit", "payment_approve", "bank_change")
    assert pack.SENSITIVE_PRIVILEGES == pack.PRIVILEGE_KINDS


def test_normal_path_is_what_the_bypass_detector_compares():
    assert pack.NORMAL_PATH["properties"] == PACK_PROPERTIES["finance"]
    assert "approvers" in FEWER_IS_BYPASS


def test_claim_vocabulary_is_the_reader_vocabulary():
    assert set(pack.CLAIM_VOCABULARY) == {k.value for k in ClaimKind if k is not ClaimKind.NONE}
    assert all(pack.CLAIM_VOCABULARY.values())


def test_finance_pack_does_not_import_the_oss_pack():
    assert imports_of(ROOT / "packs" / "finance", "packs.oss") == []


def test_the_import_scan_catches_a_bad_import(tmp_path):
    (tmp_path / "bad.py").write_text("from packs.oss import pack\nimport packs.oss.grants\n")
    assert imports_of(tmp_path, "packs.oss") == ["bad.py:1", "bad.py:2"]


def test_to_epoch():
    # 1970-01-02T00:00:00Z is exactly one day: 86400 seconds.
    assert parse.to_epoch("1970-01-02T00:00:00Z") == 86_400


def test_hid_is_stable_case_insensitive_and_hides_the_address():
    a = parse.hid("Priya.Nair@northbridge.example", SALT)
    assert a == parse.hid("priya.nair@northbridge.example", SALT)
    assert a != parse.hid("priya.nair@northbridge.example", b"other-salt")
    assert "@" not in a and "priya" not in a


def test_parsed_output_carries_no_address():
    parsed = parse.parse_records(synthetic.build()["records"], SALT)
    for p in parsed:
        for key, value in p.items():
            if key == "text":
                continue  # message text is kept for the Reader; the addresses are not in it
            assert "@" not in str(value), (p["ref"], key)


def test_unknown_source_is_refused():
    with pytest.raises(ValueError):
        parse.parse_records([{"source": "fax", "id": "1"}], SALT)


def test_email_makes_everyone_on_it_a_viewer():
    rec = next(r for r in synthetic.build()["records"] if r["id"] == "e-k01")
    p = parse.parse_email(rec, SALT)
    # sender Daniel; viewers are the AP inbox and Hannah (cc), two distinct hids
    assert p["hid"] == parse.hid(synthetic.DANIEL, SALT)
    assert len(p["seen_by"]) == 2
    assert p["place"]["kind"] == "list"


def test_dataset_is_synthetic_and_planted_ones_carry_the_campaign():
    data = synthetic.build()
    assert data["synthetic"] is True
    for r in data["records"]:
        assert r["synthetic"] is True
        assert (r["campaign_id"] == "kestrel-takeover") == r["planted"]
    planted = [r for r in data["records"] if r["planted"]]
    assert len(planted) == 13  # hand count of the §11.1 rows written in synthetic.build()


def test_dataset_on_disk_matches_the_generator():
    import json

    on_disk = json.loads((ROOT / "data" / "synthetic" / "northbridge.json").read_text("utf-8"))
    assert on_disk == json.loads(json.dumps(synthetic.build()))


def test_every_address_in_the_dataset_is_an_invented_example_address():
    import re

    text = (ROOT / "data" / "synthetic" / "northbridge.json").read_text("utf-8")
    for addr in re.findall(r"[\w.+-]+@[\w.-]+", text):
        assert addr.endswith(".example"), addr


# --- approval authority at a horizon. Policy at t=10: holders A, B, two approvers required.
POLICY = {
    "entry": "policy",
    "at": 10,
    "privilege": "bank_change",
    "approvers_required": 2,
    "holders": ["A", "B"],
}
LEAVE = {"entry": "leave", "at": 100, "hid": "A", "until": 200}


def test_both_holders_present_keep_two_approvals():
    rows = mapping.can_grant_rows([POLICY, LEAVE], as_of=50)
    assert sorted((r["hid"], r["approvals_required"]) for r in rows) == [("A", 2), ("B", 2)]


def test_a_holder_on_leave_is_dropped_and_the_other_needs_only_one():
    rows = mapping.can_grant_rows([POLICY, LEAVE], as_of=150)
    # A is away (100 <= 150 < 200): only B can approve, and min(2, 1 available) = 1.
    assert [(r["hid"], r["approvals_required"]) for r in rows] == [("B", 1)]


def test_the_holder_is_back_when_the_leave_ends():
    rows = mapping.can_grant_rows([POLICY, LEAVE], as_of=200)
    assert sorted((r["hid"], r["approvals_required"]) for r in rows) == [("A", 2), ("B", 2)]


def test_no_policy_yet_means_no_authority():
    assert mapping.can_grant_rows([POLICY], as_of=5) == []


def test_participation_rows_keep_earliest_since_and_latest_last():
    events = [
        {"hid": "a", "place": "p", "at": 30},
        {"hid": "a", "place": "p", "at": 10},
        {"hid": "a", "place": "q", "at": 20},
        {"hid": "b", "place": "p", "at": 5},
    ]
    assert who_saw.participation_rows(events) == [
        {"hid": "a", "place": "p", "since": 10, "last_at": 30},
        {"hid": "a", "place": "q", "since": 20, "last_at": 20},
        {"hid": "b", "place": "p", "since": 5, "last_at": 5},
    ]
