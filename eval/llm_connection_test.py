"""One live call to the extraction model, to prove the LLM client works end to end.

Run: python -m eval.llm_connection_test [--account-info]

Prints only: HTTP status, whether the JSON parsed, input tokens, output tokens, reasoning tokens
(if the reply gives them) and latency. Never the key and never the prompt or the reply text.
--account-info also prints whether the configured model ids exist on the account and the account's
own rate limits, as the reply's headers state them (for docs/VERIFIED.md).
"""

import sys

from pydantic import BaseModel

from core.llm.client import (
    InvalidJSON,
    LLMClient,
    LLMError,
    LLMHTTPError,
    load_config,
)

PROMPT = 'Return JSON with one field "ok" set to true.'


class Ok(BaseModel):
    ok: bool


def run(client: LLMClient | None = None) -> dict:
    """Make the call. Returns a plain dict of what happened; raises nothing for an HTTP failure."""
    config = load_config()
    client = client or LLMClient(config)
    if not client.has_key:
        return {"error": "GROQ_API_KEY is not set (add it to .env)", "http_status": None}
    try:
        result = client.complete_json(
            model=config["extraction_model"],
            prompt=PROMPT,
            schema_model=Ok,
            max_tokens=1024,
            use_cache=False,  # a connection test must really reach the server
        )
    except LLMHTTPError as e:
        return {"http_status": e.status, "json_parse": False, "error": e.detail}
    except InvalidJSON as e:
        rec = client.calls[-1]
        return {
            "http_status": rec.http_status,
            "json_parse": False,
            "error": str(e),
            **_numbers(rec),
        }
    except LLMError as e:
        return {"http_status": None, "json_parse": False, "error": str(e)}
    rec = result.record
    return {
        "http_status": rec.http_status,
        "json_parse": True,
        "ok_field": result.data.ok,
        "rate_headers": rec.rate_headers,
        **_numbers(rec),
    }


def _numbers(rec) -> dict:
    return {
        "input_tokens": rec.input_tokens,
        "output_tokens": rec.output_tokens,
        "reasoning_tokens": rec.reasoning_tokens,
        "latency_ms": round(rec.latency_ms),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = run()
    if out.get("error") and out.get("http_status") is None and "json_parse" not in out:
        print(out["error"])
        return 2
    print(f"HTTP status: {out['http_status']}")
    print(f"JSON parse: {'yes' if out['json_parse'] else 'no'}")
    if "input_tokens" in out:
        print(f"input tokens: {out['input_tokens']}")
        print(f"output tokens: {out['output_tokens']}")
        if out["reasoning_tokens"] is not None:
            print(f"reasoning tokens: {out['reasoning_tokens']}")
        print(f"latency ms: {out['latency_ms']}")
    if not out["json_parse"]:
        print(f"error: {out['error']}")
        return 1
    if "--account-info" in argv:
        _account_info(out)
    return 0


def _account_info(out: dict) -> None:
    config = load_config()
    client = LLMClient(config)
    ids = client.list_model_ids()
    for name in ("planning_model", "extraction_model"):
        print(f"{name} {config[name]} on this account: {'yes' if config[name] in ids else 'no'}")
    for header, value in sorted(out.get("rate_headers", {}).items()):
        print(f"{header}: {value}")


if __name__ == "__main__":
    sys.exit(main())
