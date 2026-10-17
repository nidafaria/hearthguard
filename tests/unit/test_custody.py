"""Unit tests for custody memory rules and Action Boundary enforcement."""

import pytest

from core.memory import custody
from core.policy import boundary


def test_custody_record_id_is_deterministic():
    id1 = custody.custody_record_id("org_test", "release", "act_01")
    id2 = custody.custody_record_id("org_test", "release", "act_01")
    assert id1 == id2
    assert "org_test" in id1
    assert "release" in id1
    assert "act_01" in id1


def test_action_boundary_strictly_refuses_blocking():
    # Section 4.4 Never: 'block a release or payment'
    with pytest.raises(boundary.BoundaryViolation) as exc_info:
        boundary.check("block_release_or_payment", recipient="owner")
    assert exc_info.value.rule == "never"


def test_action_boundary_allows_warn_and_suggest():
    # Section 4.4 Level 1 and Level 2
    assert boundary.check("send_private_note", recipient="owner") == boundary.Level.PRIVATE_NOTE
    assert boundary.check("suggest_safety_step", recipient="owner") == boundary.Level.SUGGEST_STEP
