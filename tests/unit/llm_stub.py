"""Helpers for the LLM client tests: fake chat-completion replies for the local HTTP server.

These test the client's own logic (cache, retries, rate limiting, validation). They say nothing
about Groq itself; the live test in tests/integration/test_llm_live.py does that.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from core.llm.client import LLMClient
from tests.unit.conftest import Clock

BASE_PATH = "/openai/v1"
CHAT = f"{BASE_PATH}/chat/completions"
FAKE_KEY = "gsk_TESTKEY_not_a_real_key_0123456789"


class Ok(BaseModel):
    ok: bool


class Other(BaseModel):
    ok: bool
    note: str


def completion(content, prompt_tokens=11, completion_tokens=7, reasoning=None, finish="stop"):
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if reasoning is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    body = {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": finish}
        ],
        "usage": usage,
    }
    headers = {"x-ratelimit-limit-requests": "1000", "x-ratelimit-limit-tokens": "8000"}
    return 200, headers, json.dumps(body).encode()


def error(status, message="something went wrong", kind="invalid_request_error", **headers):
    body = json.dumps({"error": {"message": message, "type": kind}}).encode()
    return status, headers, body


def make_client(site, tmp_path: Path, clock: Clock | None = None, key=FAKE_KEY, limits=None):
    """A client pointed at the local server, with a fake clock and an isolated cache folder."""
    clock = clock or Clock()
    logs: list[str] = []
    config = {
        "base_url": site.url(BASE_PATH),
        "cache_dir": str(tmp_path / "cache"),
        "rate_limit": limits or {"tokens_per_minute": 1_000_000, "requests_per_day": 100_000},
    }
    client = LLMClient(
        config,
        key=key,
        cache_dir=tmp_path / "cache",
        clock=clock.now,
        sleep=clock.sleep,
        log=logs.append,
    )
    client.test_logs = logs  # kept so a test can search them
    client.test_clock = clock
    return client
