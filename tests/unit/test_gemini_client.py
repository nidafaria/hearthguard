"""Unit tests for the Gemini LLM client.

Verifies:
  - reads key from GEMINI_API_KEY
  - never prints, logs, or stores the key
  - pricing and INR cost calculation
  - spend limit stop (raises SpendLimitReached at ₹150 or configured limit)
  - cache behavior and schema validation
  - interface compatibility with LLMClient
"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from core.llm import (
    GeminiClient,
    SpendLimitReached,
    estimate_call_cost_inr,
    get_client_for_model,
)
from core.llm.client import (
    LLMError,
    LLMHTTPError,
    strict_schema,
)
from tests.unit.conftest import Clock
from tests.unit.llm_stub import CHAT, FAKE_KEY, Ok, completion, error

MODEL = "gemini-2.0-flash"
PROMPT = "UNIQUE-GEMINI-PROMPT-987654 please answer"
GOOD = completion('{"ok": true}', prompt_tokens=1000, completion_tokens=400)


def make_gemini_client(
    site,
    tmp_path: Path,
    clock: Clock | None = None,
    key=FAKE_KEY,
    max_spend_inr=150.0,
):
    clock = clock or Clock()
    logs: list[str] = []
    base_url = site.url("/openai/v1")
    client = GeminiClient(
        key=key,
        base_url=base_url,
        cache_dir=tmp_path / "cache",
        clock=clock.now,
        sleep=clock.sleep,
        log=logs.append,
        max_spend_inr=max_spend_inr,
    )
    client.test_logs = logs
    client.test_clock = clock
    return client


def test_gemini_pricing_and_cost_estimation():
    # gemini-1.5-flash: $0.075 / 1M in, $0.30 / 1M out, USD_TO_INR = 84.00
    cost_inr = estimate_call_cost_inr("gemini-1.5-flash", 1_000_000, 1_000_000)
    expected_usd = 0.075 + 0.30  # 0.375
    expected_inr = 0.375 * 84.0  # 31.50
    assert abs(cost_inr - expected_inr) < 1e-4

    # gemini-2.0-flash: $0.10 / 1M in, $0.40 / 1M out
    cost_20 = estimate_call_cost_inr("gemini-2.0-flash", 1000, 500)
    expected_20_usd = (1000 / 1e6 * 0.10) + (500 / 1e6 * 0.40)  # 0.0001 + 0.0002 = 0.0003
    expected_20_inr = 0.0003 * 84.0  # 0.0252 INR
    assert abs(cost_20 - expected_20_inr) < 1e-6


def test_key_handling_and_no_leak(site, tmp_path):
    site.routes[CHAT] = GOOD
    client = make_gemini_client(site, tmp_path)
    result = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert result.data.ok is True

    # Key is not present in cache files or logs
    cache_files = list((tmp_path / "cache").rglob("*.json"))
    seen = "".join(p.read_text(encoding="utf-8") for p in cache_files)
    seen += "\n".join(client.test_logs)
    assert FAKE_KEY not in seen

    # Error scrubber strips key from error message
    site.routes[CHAT] = error(401, message=f"Invalid key: {FAKE_KEY}", kind="auth")
    with pytest.raises(LLMHTTPError) as exc:
        client.complete_json(model=MODEL, prompt="new prompt", schema_model=Ok, use_cache=False)
    assert FAKE_KEY not in str(exc.value)
    assert "[key removed]" in str(exc.value)


def test_missing_key_refuses_before_network(site, tmp_path):
    client = make_gemini_client(site, tmp_path, key=None)
    with pytest.raises(LLMError, match="GEMINI_API_KEY is not set"):
        client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert site.hits == []


def test_spend_limit_stop(site, tmp_path):
    site.routes[CHAT] = GOOD
    # Set limit to 0.05 INR (~2 calls with 1000 in, 400 out cost ~0.0218 each)
    client = make_gemini_client(site, tmp_path, max_spend_inr=0.03)

    # First call succeeds
    res1 = client.complete_json(model=MODEL, prompt="prompt 1", schema_model=Ok, use_cache=False)
    assert res1.data.ok is True
    assert client.cumulative_spend_inr > 0

    # Second call succeeds
    res2 = client.complete_json(model=MODEL, prompt="prompt 2", schema_model=Ok, use_cache=False)
    assert res2.data.ok is True
    # Now cumulative spend exceeds 0.03 INR
    assert client.cumulative_spend_inr >= 0.03

    # Third call raises SpendLimitReached before making any network call
    hits_before = len(site.hits)
    with pytest.raises(SpendLimitReached, match=r"spend limit of (?:₹|INR )0\.03 reached"):
        client.complete_json(model=MODEL, prompt="prompt 3", schema_model=Ok, use_cache=False)
    assert len(site.hits) == hits_before


def test_get_client_for_model_dispatch():
    groq_client = get_client_for_model("openai/gpt-oss-20b", key=None)
    assert groq_client.__class__.__name__ == "LLMClient"

    gemini_client = get_client_for_model("gemini-2.0-flash", key=None)
    assert isinstance(gemini_client, GeminiClient)


def test_gemini_cache_hit_costs_zero(site, tmp_path):
    site.routes[CHAT] = GOOD
    client = make_gemini_client(site, tmp_path)

    # Fresh call
    res1 = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok, use_cache=True)
    assert res1.record.cache_hit is False
    spend_after_call1 = client.cumulative_spend_inr

    # Cached call
    res2 = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok, use_cache=True)
    assert res2.record.cache_hit is True
    # Cache hit adds zero tokens and zero spend
    assert client.cumulative_spend_inr == spend_after_call1


def test_in_scope_message_call_with_quote_check(site, tmp_path):
    from core.claims import reader
    from eval import reader_spotcheck as rs

    # Prepare real message msg00552
    redactor = rs.build_redactor()
    head, author_hash, clean = rs.prepare(552, redactor)

    # Substring quote from msg00552
    real_quote = "There is some code for special behavior with -T0 now"
    assert real_quote in clean.text

    reply_json = json.dumps({
        "claims": [
            {
                "kind": "CAPACITY_STATEMENT",
                "quote": real_quote,
                "confidence": 0.85,
            }
        ]
    })
    site.routes[CHAT] = completion(reply_json, prompt_tokens=850, completion_tokens=120)

    client = make_gemini_client(site, tmp_path)
    res = reader.read_message(clean.text, author_hash, client=client, model=MODEL)

    assert len(res.claims) == 1
    c = res.claims[0]
    assert c.kind == "CAPACITY_STATEMENT"
    assert c.quote == real_quote
    assert c.model == MODEL
    # Exact quote verification
    assert clean.text.encode()[c.offset : c.offset + len(c.quote.encode())] == c.quote.encode()
    assert res.record.model == MODEL
    assert res.record.input_tokens == 850
    assert res.record.output_tokens == 120
    assert client.cumulative_spend_inr > 0
