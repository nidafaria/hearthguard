"""Board rules that need no server: the spec query, key shapes and the timeout rule."""

import pytest

from core.board import board
from core.board.hardening import FIELDS, record_hardening


def test_claim_query_is_the_spec_query_with_a_stable_tiebreak():
    q = board.CLAIM_QUERY
    assert "t.status = 'OPEN' OR (t.status = 'CLAIMED' AND t.lease_until < $now)" in q
    assert "ORDER BY t.priority DESC, t.created_at ASC, t.id ASC LIMIT 1" in q
    assert board.LEASE_MS == 30_000


def test_the_board_lives_in_an_org_graph():
    assert board.org_of("org_abc") == "abc"
    with pytest.raises(ValueError):
        board.org_of("playbook")


def test_note_key_is_one_per_finding_and_person():
    assert board.note_key("f1", "h1") == board.note_key("f1", "h1")
    assert board.note_key("f1", "h1") != board.note_key("f1", "h2")


def test_hardening_refuses_an_unknown_field_before_any_query():
    with pytest.raises(ValueError):
        record_hardening(None, "org_x", "x", "run", "s1", {"cost_before": 1, "guess": 2})
    assert "cost_before" in FIELDS
