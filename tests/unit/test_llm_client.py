"""LLM client logic: the request, retries, JSON validation, records, and the rate limiter.

These are unit tests of the client's own behaviour against a local HTTP server. They do not test
Groq. The live check is tests/integration/test_llm_live.py.
"""

import json

import pytest
from pydantic import BaseModel

from core.llm.client import (
    DailyLimitReached,
    InvalidJSON,
    LLMError,
    LLMHTTPError,
    RateLimiter,
    strict_schema,
)
from tests.unit.conftest import Clock
from tests.unit.llm_stub import CHAT, FAKE_KEY, Ok, completion, error, make_client

MODEL = "openai/gpt-oss-20b"
PROMPT = "UNIQUE-PROMPT-TEXT-162534 please answer"
GOOD = completion('{"ok": true}')


def call(client, **kw):
    return client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok, **kw)


def cache_entries(tmp_path):
    return [p for p in (tmp_path / "cache").glob("*.json") if len(p.stem) == 64]


# ------------------------------------------------------------------ the request
def test_the_request_asks_for_strict_json_with_the_key_in_the_header(site, tmp_path):
    site.routes[CHAT] = GOOD
    call(make_client(site, tmp_path), max_tokens=321)
    body = site.posts[0]
    assert site.hits[0][1] == f"Bearer {FAKE_KEY}"
    assert body["model"] == MODEL
    assert body["max_completion_tokens"] == 321
    assert body["temperature"] == 0
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "Ok"
    schema = fmt["json_schema"]["schema"]
    assert schema["additionalProperties"] is False and schema["required"] == ["ok"]
    assert body["messages"] == [{"role": "user", "content": PROMPT}]


def test_a_system_prompt_goes_first(site, tmp_path):
    site.routes[CHAT] = GOOD
    make_client(site, tmp_path).complete_json(
        model=MODEL, prompt="Q", schema_model=Ok, system="Be brief."
    )
    assert [m["role"] for m in site.posts[0]["messages"]] == ["system", "user"]


def test_the_schema_is_made_strict_all_the_way_down():
    class Inner(BaseModel):
        a: int
        b: str = "default"

    class Outer(BaseModel):
        items: list[Inner]
        properties: str  # a field NAMED "properties" must not be mistaken for a schema keyword
        maybe: Inner | None = None

    schema = strict_schema(Outer)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["items", "properties", "maybe"]
    inner = schema["$defs"]["Inner"]
    assert inner["additionalProperties"] is False and inner["required"] == ["a", "b"]
    assert schema["properties"]["properties"] == {"title": "Properties", "type": "string"}


# ------------------------------------------------------------------ the key stays secret
def test_the_key_appears_in_no_file_no_log_no_record_and_no_error(site, tmp_path):
    site.routes[CHAT] = GOOD
    client = make_client(site, tmp_path)
    result = call(client)
    files = [p for p in (tmp_path / "cache").rglob("*") if p.is_file()]
    seen = "".join(p.read_text(encoding="utf-8") for p in files)
    seen += "\n".join(client.test_logs) + json.dumps(result.record.as_dict())
    assert FAKE_KEY not in seen

    # An error body that echoes the key back is scrubbed before it reaches the exception.
    site.routes[CHAT] = error(401, message=f"Invalid API key {FAKE_KEY}", kind="auth")
    with pytest.raises(LLMHTTPError) as exc:
        call(client, use_cache=False)
    assert exc.value.status == 401
    assert FAKE_KEY not in str(exc.value) and "[key removed]" in str(exc.value)
    assert PROMPT not in str(exc.value)


def test_with_no_key_it_refuses_before_any_request(site, tmp_path):
    client = make_client(site, tmp_path, key=None)
    with pytest.raises(LLMError, match="GROQ_API_KEY is not set"):
        call(client)
    assert site.hits == []


# ------------------------------------------------------------------ the record of a call
def test_every_call_is_recorded_with_tokens_latency_and_hash(site, tmp_path):
    site.routes[CHAT] = completion(
        '{"ok": true}', prompt_tokens=21, completion_tokens=9, reasoning=4
    )
    client = make_client(site, tmp_path)
    rec = call(client).record
    assert (rec.input_tokens, rec.output_tokens, rec.reasoning_tokens) == (21, 9, 4)
    assert rec.model == MODEL and rec.http_status == 200 and rec.json_valid and not rec.cache_hit
    assert len(rec.prompt_sha256) == 64 and len(rec.cache_key) == 64 and rec.latency_ms >= 0
    assert rec.rate_headers["x-ratelimit-limit-tokens"] == "8000"
    assert client.calls == [rec]
    log_line = (tmp_path / "cache" / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0]
    logged = json.loads(log_line)
    assert logged["input_tokens"] == 21 and PROMPT not in log_line


def test_reasoning_tokens_are_none_when_the_reply_does_not_report_them(site, tmp_path):
    site.routes[CHAT] = GOOD
    assert call(make_client(site, tmp_path)).record.reasoning_tokens is None


# ------------------------------------------------------------------ retries
def test_a_429_waits_for_retry_after_then_succeeds(site, tmp_path):
    limited = error(429, "slow down", "rate_limit", **{"retry-after": "7"})
    site.routes[CHAT] = lambda n: limited if n == 1 else GOOD
    client = make_client(site, tmp_path)
    result = call(client)
    assert result.data.ok and result.record.attempts == 2 and len(site.posts) == 2
    assert any(7 <= s <= 9 for s in client.test_clock.sleeps)


def test_a_5xx_is_retried_with_backoff(site, tmp_path):
    site.routes[CHAT] = lambda n: error(503) if n <= 2 else GOOD
    client = make_client(site, tmp_path)
    result = call(client)
    assert result.record.attempts == 3
    assert client.test_clock.sleeps[:2] == [1.0, 2.0]  # backoff doubles


def test_it_gives_up_after_three_retries(site, tmp_path):
    site.routes[CHAT] = error(500)
    with pytest.raises(LLMError, match="after 3 retries"):
        call(make_client(site, tmp_path))
    assert len(site.posts) == 4  # the first try and three retries


def test_a_4xx_other_than_429_is_not_retried_and_the_error_carries_no_prompt(site, tmp_path):
    site.routes[CHAT] = error(400, message="schema is not valid", kind="invalid_request_error")
    with pytest.raises(LLMHTTPError) as exc:
        call(make_client(site, tmp_path))
    assert exc.value.status == 400 and "schema is not valid" in exc.value.detail
    assert len(site.posts) == 1 and PROMPT not in str(exc.value)


# ------------------------------------------------------------------ JSON validation
def test_invalid_json_is_asked_again_and_tokens_add_up(site, tmp_path):
    bad = completion("not json at all", 10, 5)
    good = completion('{"ok": true}', 10, 3)
    site.routes[CHAT] = lambda n: bad if n == 1 else good
    rec = call(make_client(site, tmp_path)).record
    assert rec.attempts == 2 and len(site.posts) == 2
    assert (rec.input_tokens, rec.output_tokens) == (20, 8)


def test_a_reply_that_does_not_match_the_schema_counts_as_invalid(site, tmp_path):
    wrong_type = completion('{"ok": "yes"}')
    site.routes[CHAT] = lambda n: wrong_type if n == 1 else GOOD
    assert call(make_client(site, tmp_path)).data.ok is True and len(site.posts) == 2


def test_after_three_bad_replies_it_raises_and_says_what_was_wrong(site, tmp_path):
    site.routes[CHAT] = completion('{"wrong": 1}')
    client = make_client(site, tmp_path)
    with pytest.raises(InvalidJSON) as exc:
        call(client)
    assert len(site.posts) == 3  # one try and two retries
    assert "3 attempts" in str(exc.value) and "ok" in str(exc.value)
    assert '{"wrong"' not in str(exc.value) and PROMPT not in str(exc.value)
    assert client.calls[-1].json_valid is False and client.calls[-1].http_status == 200
    assert cache_entries(tmp_path) == []  # an invalid reply is never cached


def test_a_truncated_reply_is_reported_as_unparseable_with_its_finish_reason(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": tr', finish="length")
    with pytest.raises(InvalidJSON, match="finish_reason=length"):
        call(make_client(site, tmp_path))


# ------------------------------------------------------------------ the rate limiter
def limiter(tmp_path, clock, **limits):
    return RateLimiter(
        limits,
        usage_path=tmp_path / "usage.json",
        clock=clock.now,
        sleep=clock.sleep,
        log=lambda _: None,
    )


def test_it_sleeps_until_the_minute_window_has_room(tmp_path):
    clock = Clock()
    rl = limiter(tmp_path, clock, tokens_per_minute=1000)
    rl.before("m", 600)
    assert clock.sleeps == []
    rl.before("m", 600)  # 600 + 600 > 1000: must wait for the first to leave the window
    assert len(clock.sleeps) == 1 and 60 <= clock.sleeps[0] <= 61


def test_the_real_token_count_replaces_the_estimate(tmp_path):
    clock = Clock()
    rl = limiter(tmp_path, clock, tokens_per_minute=1000)
    slot = rl.before("m", 600)
    rl.settle("m", slot, 200)  # the call really used 200
    rl.before("m", 600)  # 200 + 600 fits, so no wait
    assert clock.sleeps == []


def test_the_requests_per_minute_limit_sleeps(tmp_path):
    clock = Clock()
    rl = limiter(tmp_path, clock, requests_per_minute=2)
    rl.before("m", 1)
    rl.before("m", 1)
    assert clock.sleeps == []
    rl.before("m", 1)
    assert len(clock.sleeps) == 1 and 60 <= clock.sleeps[0] <= 61


def test_one_request_bigger_than_the_minute_limit_is_refused_not_waited_for(tmp_path):
    with pytest.raises(LLMError, match="exceeds 1000"):
        limiter(tmp_path, Clock(), tokens_per_minute=1000).before("m", 1500)


def test_the_daily_request_limit_raises_and_survives_a_restart(tmp_path):
    clock = Clock()
    rl = limiter(tmp_path, clock, requests_per_day=3)
    for _ in range(3):
        rl.before("m", 1)
    with pytest.raises(DailyLimitReached, match="3 requests per day"):
        rl.before("m", 1)
    with pytest.raises(DailyLimitReached):  # a brand-new limiter reads the saved count
        limiter(tmp_path, clock, requests_per_day=3).before("m", 1)
    assert clock.sleeps == []  # it refused; it did not sleep for hours


def test_the_daily_token_limit_raises(tmp_path):
    rl = limiter(tmp_path, Clock(), tokens_per_day=1000)
    rl.before("m", 700)
    with pytest.raises(DailyLimitReached, match="tokens per day"):
        rl.before("m", 700)


def test_daily_counters_reset_at_midnight_utc(tmp_path):
    clock = Clock(start=86_400 * 20_000 + 86_000)  # 400 seconds before midnight UTC
    rl = limiter(tmp_path, clock, requests_per_day=1)
    rl.before("m", 1)
    with pytest.raises(DailyLimitReached):
        rl.before("m", 1)
    clock.t += 500  # past midnight
    rl.before("m", 1)


def test_each_model_has_its_own_limits(tmp_path):
    rl = limiter(tmp_path, Clock(), requests_per_day=1)
    rl.before("model-a", 1)
    rl.before("model-b", 1)  # a different model is not affected
    with pytest.raises(DailyLimitReached):
        rl.before("model-a", 1)


def test_an_explicit_no_key_stays_no_key_even_when_the_environment_has_one(monkeypatch):
    # Tests must never pick up the real key from .env: key=None means no key.
    from core.llm.client import LLMClient

    monkeypatch.setenv("GROQ_API_KEY", "gsk_from_the_environment")
    config = {"base_url": "http://127.0.0.1:9", "rate_limit": {}}
    assert LLMClient(config, key=None).has_key is False
    assert LLMClient(config, key="explicit").has_key is True
    assert LLMClient(config).has_key is True  # leaving it out reads the environment
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert LLMClient(config).has_key is False
