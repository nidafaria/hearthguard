"""One live call to Groq. Skipped unless GROQ_API_KEY is set (in the environment or .env).

This is the only test that reaches the real service. It prints nothing: not the key, not the
prompt, not the reply.
"""

import os

import pytest
from dotenv import load_dotenv

from eval import llm_connection_test

load_dotenv()
HAS_KEY = bool(os.environ.get("GROQ_API_KEY", "").strip())

pytestmark = pytest.mark.skipif(
    not HAS_KEY,
    reason="GROQ_API_KEY is not set, so the live Groq call was skipped (add it to .env to run it)",
)


def test_the_live_call_returns_status_200_and_valid_json():
    out = llm_connection_test.run()
    assert out["http_status"] == 200, out.get("error")
    assert out["json_parse"] is True
    assert out["ok_field"] is True
    assert out["input_tokens"] > 0 and out["output_tokens"] > 0
    assert out["latency_ms"] >= 0
