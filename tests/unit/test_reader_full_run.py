"""The public summary of the full Reader run: counts only, no quotes, no hashed ids, no text."""

import json

from eval import reader_full_run as rfr


def saved():
    return {
        "msg00001": {
            "message_id": "msg00001",
            "date_utc": "2022-01-01T00:00:00Z",
            "author_hash": "a" * 64,
            "claims": [
                {"kind": "PRESSURE", "quote": "SECRET QUOTE TEXT", "offset": 3, "confidence": 0.9},
                {"kind": "URGENCY", "quote": "ANOTHER QUOTE", "offset": 9, "confidence": 0.5},
            ],
            "rejections": ["quote is not a substring of the message text"],
            "none_items": 1,
            "skipped": None,
            "tokens": {"input": 100, "output": 50, "reasoning": 40},
            "cache_hit": False,
        },
        "msg00002": {
            "message_id": "msg00002",
            "date_utc": "2022-01-02T00:00:00Z",
            "author_hash": "b" * 64,
            "claims": [],
            "rejections": [],
            "none_items": 0,
            "skipped": rfr.TOO_LONG,
            "tokens": None,
            "cache_hit": None,
        },
        "msg00003": {
            "message_id": "msg00003",
            "date_utc": "2022-01-03T00:00:00Z",
            "author_hash": "c" * 64,
            "claims": [],
            "rejections": [],
            "none_items": 0,
            "skipped": rfr.NO_VALID_JSON,
            "tokens": None,
            "cache_hit": None,
        },
    }


def test_summary_counts_match_the_saved_entries():
    doc = rfr.public_summary(saved(), 5)
    t = doc["totals"]
    # 2 claims (1 PRESSURE, 1 URGENCY), 1 rejection, 1 none item; tokens only from msg00001.
    assert doc["messages_in_scope_total"] == 5 and doc["messages_done"] == 3
    assert t["claims"] == 2 and t["claims_by_kind"] == {"PRESSURE": 1, "URGENCY": 1}
    assert t["rejections"] == 1 and t["none_items"] == 1
    assert (t["input_tokens"], t["output_tokens"], t["reasoning_tokens"]) == (100, 50, 40)
    assert t["messages_not_read_too_long"] == 1 and t["messages_not_read_no_valid_json"] == 1
    assert t["messages_without_claims"] == 2


def test_summary_holds_no_quote_no_hash_and_no_at_sign():
    text = json.dumps(rfr.public_summary(saved(), 3))
    assert "SECRET QUOTE TEXT" not in text and "ANOTHER QUOTE" not in text
    assert "a" * 64 not in text and "b" * 64 not in text
    assert "@" not in text
