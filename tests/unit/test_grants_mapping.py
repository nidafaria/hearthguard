"""Source records -> grant edges (spec §6.1). Pure mapping on hand-built records, no database."""

import pytest

from packs.oss.grants import RefusedRecord, map_records

GOOD_GRANT = {
    "source": "MAINTAINERS", "kind": "grant", "actor": "h1", "privilege": "release",
    "at": 100, "by": "h0", "ref": "MAINTAINERS@abc",
}  # fmt: skip
GOOD_CAN = {
    "source": "CODEOWNERS", "kind": "can_grant", "actor": "h0", "privilege": "release",
    "approvals_required": 2, "ref": "CODEOWNERS@abc",
}  # fmt: skip
GOOD_APPROVAL = {
    "source": "pr_review", "kind": "approval", "actor": "h0", "action_ref": "sha1", "at": 110,
    "ref": "pr/12",
}  # fmt: skip


def test_hand_built_records_map_to_the_four_edge_kinds():
    m = map_records([GOOD_GRANT, GOOD_CAN, GOOD_APPROVAL])
    # Hand-worked: one GRANTED, one CAN_GRANT (2 approvals), one APPROVED, privilege 'release'.
    assert m.privileges == {"release"}
    assert [(g["hid"], g["kind"], g["at"], g["by"]) for g in m.granted] == [
        ("h1", "release", 100, "h0")
    ]
    assert [(c["hid"], c["approvals_required"]) for c in m.can_grant] == [("h0", 2)]
    assert [(a["hid"], a["ref"], a["at"]) for a in m.approved] == [("h0", "sha1", 110)]


def test_no_records_map_to_nothing():
    m = map_records([])
    assert (m.privileges, m.granted, m.can_grant, m.approved) == (set(), [], [], [])


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD_GRANT, "source": "twitter"},  # undocumented source
        {**GOOD_GRANT, "source": None},
        {**GOOD_GRANT, "kind": "rumour"},
        {**GOOD_GRANT, "ref": ""},  # nothing without a place to check it
        {**GOOD_GRANT, "actor": None},
        {**GOOD_GRANT, "privilege": "root"},  # not an OSS privilege
        {**GOOD_GRANT, "at": None},  # a grant needs a time
        {**GOOD_CAN, "privilege": "deploy"},
        {**GOOD_APPROVAL, "action_ref": None},
        {**GOOD_APPROVAL, "at": None},
    ],
)
def test_each_rule_refuses_its_bad_record(bad):
    with pytest.raises(RefusedRecord):
        map_records([bad])


def test_one_bad_record_refuses_the_whole_batch_and_guesses_nothing():
    """Try to break it: a good record next to a bad one must not leak the good one through."""
    with pytest.raises(RefusedRecord):
        map_records([GOOD_GRANT, {**GOOD_GRANT, "privilege": "root"}])


def test_a_missing_approvals_field_defaults_to_one_and_is_recorded_as_one():
    rec = {k: v for k, v in GOOD_CAN.items() if k != "approvals_required"}
    assert map_records([rec]).can_grant[0]["approvals_required"] == 1
