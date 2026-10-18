"""One test call on one in-scope message with the Gemini client.

Used to verify:
  - GeminiClient connects and receives structured JSON for ReaderReply
  - Tokens, latency, and estimated cost in INR (against official Google pricing)
  - Exact quote substring check against the cleaned message text
  - Key is never exposed or logged
"""

import json
import sys
from pathlib import Path

from core.claims import reader
from core.llm.gemini import (
    DEFAULT_MAX_SPEND_INR,
    PRICING_SOURCE,
    USD_TO_INR,
    GeminiClient,
    estimate_call_cost_inr,
)
from eval import reader_full_run as rfr
from eval import reader_spotcheck as rs


def run_one_test_call(
    model: str = "gemini-3.8-flash",
    msg_num: int = 552,
) -> dict:
    client = GeminiClient(max_spend_inr=DEFAULT_MAX_SPEND_INR)
    if not client.has_key:
        print("ERROR: GEMINI_API_KEY is not set in .env or environment.")
        print("Please add GEMINI_API_KEY=<your-key> to .env and re-run.")
        return {"error": "missing_key"}

    redactor = rs.build_redactor()
    head, author_hash, clean = rs.prepare(msg_num, redactor)

    print(f"Making one test call on message msg{msg_num:05d} with model '{model}'...")
    res = reader.read_message(
        clean.text,
        author_hash,
        client=client,
        model=model,
        use_cache=False,
    )

    rec = res.record
    in_tok = rec.input_tokens if rec else 0
    out_tok = rec.output_tokens if rec else 0
    cost_inr = estimate_call_cost_inr(model, in_tok, out_tok)

    # Verify quote check: every accepted claim's quote must be an exact substring of clean.text
    quote_checks = []
    for c in res.claims:
        passed = (c.quote in clean.text) and (clean.text.encode()[c.offset : c.offset + len(c.quote.encode())] == c.quote.encode())
        quote_checks.append({
            "kind": c.kind,
            "quote": c.quote,
            "offset": c.offset,
            "confidence": c.confidence,
            "passed": passed,
        })

    all_passed = all(q["passed"] for q in quote_checks) if quote_checks else True

    report = {
        "message_id": rs.msg_id(msg_num),
        "model": model,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "latency_ms": round(rec.latency_ms, 2) if rec else 0.0,
        "cost_inr": round(cost_inr, 6),
        "cost_usd": round(cost_inr / USD_TO_INR, 8),
        "usd_to_inr_rate": USD_TO_INR,
        "pricing_source": PRICING_SOURCE,
        "cumulative_spend_inr": round(client.cumulative_spend_inr, 4),
        "spend_limit_inr": client.max_spend_inr,
        "claims_count": len(res.claims),
        "quote_check_passed": all_passed,
        "claims": quote_checks,
        "rejections": [r.reason for r in res.rejections],
        "none_items": res.none_items,
        "skipped": res.skipped,
    }
    return report


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.8-flash"
    result = run_one_test_call(model=model_name)
    print(json.dumps(result, indent=2))
