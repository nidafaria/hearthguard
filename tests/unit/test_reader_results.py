"""The committed Reader spot-check files agree with each other and with the source text.

Checks that need the cached mailing-list pages (git-ignored) are skipped when the cache is absent,
for example on a fresh clone. The structural checks always run.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from core.claims import reader
from eval import reader_spotcheck as rs
from packs.oss import mail_cache

RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"
SAMPLE = RESULTS / "reader_sample.json"
SPOT = RESULTS / "reader_spotcheck.json"
HAND = RESULTS / "reader_handcheck.md"

needs_files = pytest.mark.skipif(
    not (SAMPLE.exists() and SPOT.exists()), reason="spot check not run"
)
needs_cache = pytest.mark.skipif(
    not (mail_cache.RAW_ROOT / "index.json").exists(), reason="mail cache absent (git-ignored)"
)


@pytest.fixture(scope="module")
def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def spot():
    return json.loads(SPOT.read_text(encoding="utf-8"))


@needs_files
def test_the_sample_is_exactly_20_ids_on_the_stated_grid(sample):
    ids = [int(i.removeprefix("msg")) for i in sample["ids"]]
    assert len(ids) == sample["count"] == 20 == len(set(ids))
    assert ids == sorted(ids) and 512 in ids
    assert all((i - 512) % 15 == 0 and 397 <= i <= 696 for i in ids)
    assert ids == list(range(407, 693, 15))


@needs_files
def test_the_spot_check_has_one_entry_per_sampled_message(sample, spot):
    assert [m["message_id"] for m in spot["messages"]] == sample["ids"]
    assert spot["totals"]["messages"] == 20


@needs_files
def test_the_totals_add_up_from_the_entries(spot):
    ms = spot["messages"]
    t = spot["totals"]
    assert t["claims"] == sum(m["claim_count"] for m in ms) == sum(len(m["claims"]) for m in ms)
    assert (
        t["rejections"]
        == sum(m["rejection_count"] for m in ms)
        == sum(len(m["rejections"]) for m in ms)
    )
    assert t["input_tokens"] == sum(m["tokens"]["input"] for m in ms)
    assert t["output_tokens"] == sum(m["tokens"]["output"] for m in ms)
    assert t["reasoning_tokens"] == sum(m["tokens"]["reasoning"] for m in ms)
    assert t["input_tokens"] + t["output_tokens"] <= rs.TOKEN_BUDGET


@needs_files
def test_the_spot_check_file_holds_no_email_url_or_full_body(spot):
    text = json.dumps(spot, ensure_ascii=False)
    assert "@" not in text and "http" not in text
    assert all(
        len(m["text_sha256"]) == 64 and len(m["author_hash"]) == 64 for m in spot["messages"]
    )
    for m in spot["messages"]:
        for c in m["claims"]:
            assert len(c["quote"].split()) <= reader.MAX_QUOTE_WORDS
            assert 0 <= c["confidence"] <= 1
        assert "text" not in m and "body" not in m


@needs_files
@needs_cache
def test_every_recorded_quote_is_an_exact_substring_at_its_recorded_offset(spot):
    redactor = rs.build_redactor()
    checked = 0
    for m in spot["messages"]:
        n = int(m["message_id"].removeprefix("msg"))
        _, author_hash, clean = rs.prepare(n, redactor)
        assert hashlib.sha256(clean.text.encode("utf-8")).hexdigest() == m["text_sha256"]
        assert author_hash == m["author_hash"] and len(clean.text) == m["text_chars"]
        raw = clean.text.encode("utf-8")
        for c in m["claims"]:
            assert c["quote"] in clean.text
            assert (
                raw[c["offset"] : c["offset"] + len(c["quote"].encode("utf-8"))]
                == c["quote"].encode()
            )
            checked += 1
    print(f"\n[results] {checked} recorded claims checked against the rebuilt text")


@needs_files
@needs_cache
def test_no_known_sender_name_is_in_the_spot_check_output(spot):
    redactor = rs.build_redactor()
    text = json.dumps(spot, ensure_ascii=False)
    for name in [*redactor.full_names, *redactor.tokens]:
        assert not re.search(rf"\b{re.escape(name)}\b", text)


@pytest.mark.skipif(not HAND.exists(), reason="hand-check not written")
def test_the_hand_check_has_20_lines_matching_the_sample_and_says_it_is_a_spot_check():
    text = HAND.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.startswith("msg")]
    assert len(lines) == 20
    ids = json.loads(SAMPLE.read_text(encoding="utf-8"))["ids"]
    assert [ln.split(" | ")[0] for ln in lines] == ids
    assert "spot check of 20" in text and "not a precision or recall claim" in text
    assert "@" not in text
    for ln in lines:
        returned, correct, wrong, missing = (
            int(re.search(r"(\d+)", part).group(1)) for part in ln.split(" | ")[1:5]
        )
        assert correct + wrong <= returned
