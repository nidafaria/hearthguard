"""Run the frozen Reader once on the labelled test set and save the raw results.

Run:  python -m eval.reader_testrun [--token-cap N]

It refuses to start unless
  - the Reader still matches its freeze (eval/results/reader_frozen.json),
  - a person has filled in every label on the sheet (so the run cannot come before the labels),
  - every cleaned text on the sheet still matches the hash recorded when the sheet was made, and
  - the projected token cost is within the cap (60,000 by default; READER_TOKEN_CAP, --token-cap).
The projection uses the cost per message MEASURED in the 20-message spot check; it is a projection
until the run is done, and the real count is what gets saved.

The Reader is given the cleaned text from the SHEET, the text the person labelled, with the author
hash recorded in eval/results/reader_testset.json. The run happens once: an existing
reader_testrun.json is not overwritten.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

from core.claims import reader
from core.llm.client import LLMClient, load_config
from eval import reader_freeze as rf
from eval import reader_sheet as sheet
from eval import reader_spotcheck as rs

RESULTS = Path(__file__).resolve().parent / "results"
TESTRUN_PATH = RESULTS / "reader_testrun.json"
DEFAULT_TOKEN_CAP = 60_000
PROJECT_AFTER = 3  # fresh calls before the running total is projected against the cap


class TokenCapExceeded(RuntimeError):
    pass


def tokens_per_message_measured() -> float:
    """Mean tokens per message in the spot check (input plus output), from the saved file."""
    doc = json.loads(rs.OUT_PATH.read_text(encoding="utf-8"))
    used = [m["tokens"]["input"] + m["tokens"]["output"] for m in doc["messages"] if m["tokens"]]
    return sum(used) / len(used)


def projected_tokens(n_messages: int) -> int:
    return math.ceil(tokens_per_message_measured() * n_messages)


def token_cap(cli: int | None) -> int:
    if cli:
        return cli
    env = os.environ.get("READER_TOKEN_CAP", "").strip()
    return int(env) if env else DEFAULT_TOKEN_CAP


def load_inputs():
    frozen = rf.load_frozen()
    testset = json.loads(sheet.TESTSET_PATH.read_text(encoding="utf-8"))
    rows = sheet.read_sheet()
    return frozen, testset, rows


def run(cap: int | None = None, client: LLMClient | None = None) -> int:
    frozen, testset, rows = load_inputs()
    if frozen is None or rf.mismatches(frozen):
        print(
            "The Reader no longer matches its freeze, "
            "so this test would not be of the frozen prompt."
        )
        print(
            "Do not run it. Log the change with: "
            "python -m eval.reader_freeze --new-version --reason ..."
        )
        return 1
    check = sheet.check_labels(rows, testset)
    if not check.complete:
        print("The labels are not complete, so the Reader has NOT been run. Problems:")
        print("\n".join("  " + line for line in check.describe()))
        return 1
    if TESTRUN_PATH.exists():
        print(f"{TESTRUN_PATH.name} already exists. The test is run once; not overwriting it.")
        return 0

    cap = token_cap(cap)
    projected = projected_tokens(len(rows))
    if projected > cap:
        print(
            f"Stopped before any call: {len(rows)} messages are projected at about "
            f"{projected:,} tokens "
            f"({tokens_per_message_measured():.0f} per message, measured on the spot check), "
            "over the "
            f"{cap:,} cap. Raise the cap on purpose with --token-cap or READER_TOKEN_CAP."
        )
        return 5

    client = client or LLMClient(load_config())
    if not client.has_key:
        print("GROQ_API_KEY is not set (add it to .env)")
        return 2
    by_id = {m["message_id"]: m for m in testset["messages"]}
    results, fresh_tokens, fresh_calls = [], 0, 0
    for row in rows:
        mid = row["message_id"]
        text = sheet.normalise(row["cleaned_text"])
        res = reader.read_message(text, by_id[mid]["author_hash"], client=client)
        rec = res.record
        if rec is not None and not rec.cache_hit:
            fresh_tokens += rec.input_tokens + rec.output_tokens
            fresh_calls += 1
        if fresh_tokens > cap:
            raise TokenCapExceeded(
                f"{fresh_tokens} tokens used, over the {cap} cap; stopped at {mid}"
            )
        if fresh_calls == PROJECT_AFTER and len(results) + 1 < len(rows):
            proj = fresh_tokens / fresh_calls * len(rows)
            if proj > cap:
                raise TokenCapExceeded(
                    f"projected {proj:.0f} tokens, over the {cap} cap; stopped at {mid}"
                )
        results.append(_entry(mid, res))
        print(f"{mid}: {len(res.claims)} claims, {len(res.rejections)} rejected")

    tok = [r["tokens"] for r in results if r["tokens"]]
    doc = {
        "what": "Raw results of the frozen Reader on the labelled test set. Run once.",
        "reader_frozen_version": frozen["version"],
        "reader_frozen_components": frozen["components"],
        "token_cap_used": cap,
        "messages": len(results),
        "totals": {
            "claims": sum(r["claim_count"] for r in results),
            "rejections": sum(r["rejection_count"] for r in results),
            "input_tokens": sum(t["input"] for t in tok),
            "output_tokens": sum(t["output"] for t in tok),
            "reasoning_tokens": sum(t["reasoning"] or 0 for t in tok),
            "cache_hits": sum(1 for r in results if r["cache_hit"]),
        },
        "results": results,
    }
    TESTRUN_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {TESTRUN_PATH.name}: {doc['totals']}")
    return 0


def _entry(mid: str, res: reader.ReadResult) -> dict:
    rec = res.record
    return {
        "message_id": mid,
        "claim_count": len(res.claims),
        "claims": [
            {"kind": c.kind, "quote": c.quote, "offset": c.offset, "confidence": c.confidence}
            for c in res.claims
        ],
        "rejection_count": len(res.rejections),
        "rejections": [{"kind": r.kind, "reason": r.reason} for r in res.rejections],
        "none_items": res.none_items,
        "skipped": res.skipped,
        "tokens": None
        if rec is None
        else {
            "input": rec.input_tokens,
            "output": rec.output_tokens,
            "reasoning": rec.reasoning_tokens,
        },
        "cache_hit": None if rec is None else rec.cache_hit,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-cap", type=int, default=None)
    args = ap.parse_args(argv)
    return run(args.token_cap)


if __name__ == "__main__":
    sys.exit(main())
