"""Run the frozen Reader (version 1) on the in-scope xz-devel messages, resumable day by day.

Run:  python -m eval.reader_full_run

Which messages: every in-scope message in the mail cache (2021-01-01 to 2024-12-31), except the
60 in eval/results/reader_testset.json. Those are the human-labelled test set; they are read by
`make reader-score` after the labels exist, so no one sees Reader output before labelling.
The 20 spot-check messages are included: their replies are already cached, so they cost nothing.

The Reader prompt is not changed here. The run refuses if the freeze no longer matches.

Resuming: every reply is cached by the LLM client, and the per-message result is saved to
data/derived/reader_claims.json (git-ignored: it holds quotes, which are message text). A rerun
skips messages already saved. When a daily limit is reached the run stops and writes
eval/results/reader_full_progress.json with the exact number remaining.

Writes eval/results/reader_full_run.json when all messages are done: per-message claim and
rejection counts, rejection reasons and token totals. No quotes, names, emails or bodies.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from core.claims import reader
from core.llm import SpendLimitReached, get_client_for_model
from core.llm.client import (
    DailyLimitReached,
    InvalidJSON,
    LLMClient,
    LLMError,
    LLMHTTPError,
    load_config,
)
from eval import reader_freeze as rf
from eval import reader_spotcheck as rs
from packs.oss import mail_cache

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived" / "reader_claims.json"
TOO_LONG = "too long for one request under the 8,000 tokens a minute limit; not read"
NO_VALID_JSON = "the model could not return valid JSON for this message; not read"
PROGRESS = ROOT / "eval" / "results" / "reader_full_progress.json"
OUT = ROOT / "eval" / "results" / "reader_full_run.json"
TESTSET = ROOT / "eval" / "results" / "reader_testset.json"


def in_scope_ids() -> list[int]:
    rows = mail_cache.build_index()
    return sorted(r["msg"] for r in rows if r["status"] == 200 and r["in_scope"])


def excluded_ids() -> set[int]:
    if not TESTSET.exists():
        return set()
    doc = json.loads(TESTSET.read_text(encoding="utf-8"))
    return {int(m["message_id"].removeprefix("msg")) for m in doc["messages"]}


def load_saved() -> dict:
    if DERIVED.exists():
        return json.loads(DERIVED.read_text(encoding="utf-8"))
    return {}


def save(saved: dict) -> None:
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    DERIVED.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")


def entry(n: int, head: dict, author_hash: str | None, res: reader.ReadResult) -> dict:
    rec = res.record
    model = rec.model if rec is not None else None
    return {
        "message_id": rs.msg_id(n),
        "date_utc": head["date"].isoformat().replace("+00:00", "Z") if head["date"] else None,
        "author_hash": author_hash,
        "model": model,
        "claims": [
            {
                "kind": c.kind,
                "quote": c.quote,
                "offset": c.offset,
                "confidence": c.confidence,
                "model": getattr(c, "model", None) or model,
            }
            for c in res.claims
        ],
        "rejections": [r.reason for r in res.rejections],
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


def public_summary(saved: dict, todo_total: int) -> dict:
    items = [saved[k] for k in sorted(saved)]
    kinds: dict = {}
    reasons: dict = {}
    for e in items:
        for c in e["claims"]:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        for r in e["rejections"]:
            reasons[r] = reasons.get(r, 0) + 1
    tok = [e["tokens"] for e in items if e["tokens"]]
    fresh = [e["tokens"] for e in items if e["tokens"] and not e["cache_hit"]]
    return {
        "reader_frozen_version": rf.load_frozen()["version"],
        "model": load_config()["extraction_model"],
        "excluded": "the human-labelled test set (reader_testset.json), read later by reader-score",
        "messages_in_scope_total": todo_total,
        "messages_done": len(items),
        "totals": {
            "claims": sum(len(e["claims"]) for e in items),
            "claims_by_kind": dict(sorted(kinds.items())),
            "rejections": sum(len(e["rejections"]) for e in items),
            "rejections_by_reason": dict(sorted(reasons.items())),
            "none_items": sum(e["none_items"] for e in items),
            "messages_without_claims": sum(1 for e in items if not e["claims"]),
            "messages_not_read_too_long": sum(1 for e in items if e["skipped"] == TOO_LONG),
            "messages_not_read_no_valid_json": sum(
                1 for e in items if e["skipped"] == NO_VALID_JSON
            ),
            "input_tokens": sum(t["input"] for t in tok),
            "output_tokens": sum(t["output"] for t in tok),
            "reasoning_tokens": sum(t["reasoning"] or 0 for t in tok),
            "fresh_calls": len(fresh),
            "cache_hits": sum(1 for e in items if e["cache_hit"]),
        },
        "messages": [
            {
                "message_id": e["message_id"],
                "date_utc": e["date_utc"],
                "model": e.get("model"),
                "claim_count": len(e["claims"]),
                "rejection_count": len(e["rejections"]),
                "rejection_reasons": e["rejections"],
                "tokens": e["tokens"],
                "cache_hit": e["cache_hit"],
            }
            for e in items
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Reader on in-scope messages.")
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=None,
        help="Maximum number of new messages to read in this run",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model to use for extraction (defaults to extraction_model in config/models.yaml)",
    )
    args = parser.parse_args(argv)
    batch_size = args.batch_size
    model = args.model or load_config()["extraction_model"]

    bad = rf.mismatches(rf.load_frozen())
    if bad:
        print("The Reader no longer matches its freeze:", ", ".join(bad))
        return 1
    client = get_client_for_model(model, config=load_config())
    if not client.has_key:
        key_var = "GEMINI_API_KEY" if model.startswith("gemini") else "GROQ_API_KEY"
        print(f"{key_var} is not set (add it to .env)")
        return 2
    skip = excluded_ids()
    todo = [n for n in in_scope_ids() if n not in skip]
    saved = load_saved()
    redactor = rs.build_redactor()
    stop = None
    batch_done = 0
    for n in todo:
        key = rs.msg_id(n)
        if key in saved:
            continue
        if batch_size is not None and batch_done >= batch_size:
            stop = f"batch limit of {batch_size} reached"
            break
        head, author_hash, clean = rs.prepare(n, redactor)
        try:
            res = reader.read_message(clean.text, author_hash, client=client, model=model)
        except (DailyLimitReached, SpendLimitReached) as exc:
            stop = str(exc)
            break
        except (InvalidJSON, LLMHTTPError) as exc:
            if isinstance(exc, LLMHTTPError) and exc.status != 400:
                raise
            # The model could not produce JSON that fits the schema for this message (the server
            # says so with HTTP 400). The same input at temperature 0 gives the same failure, so it
            # is recorded as not read and counted, never retried until it passes or guessed.
            res = reader.ReadResult(skipped=NO_VALID_JSON)
        except LLMError as exc:
            if "exceeds" not in str(exc) or "per minute" not in str(exc):
                raise
            # One request cannot fit the account's per-minute token limit. The frozen Reader sends
            # the whole message, so it is not cut or split: it is recorded as not read.
            res = reader.ReadResult(skipped=TOO_LONG)
        saved[key] = entry(n, head, author_hash, res)
        batch_done += 1
        save(saved)
        # Requirement 3: Save progress to eval/results/reader_full_progress.json after each message
        rem = [rs.msg_id(x) for x in todo if rs.msg_id(x) not in saved]
        cur_progress = {
            "updated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(todo),
            "done": len(todo) - len(rem),
            "remaining": len(rem),
            "stopped_because": None,
            "next_message_id": rem[0] if rem else None,
        }
        PROGRESS.write_text(json.dumps(cur_progress, indent=2), encoding="utf-8")
        print(
            f"[{len(saved)}/{len(todo)}] {key} read "
            f"(claims: {len(res.claims)}, skipped: {res.skipped})",
            flush=True,
        )
        if hasattr(client, "cumulative_spend_inr") and hasattr(client, "max_spend_inr"):
            if client.cumulative_spend_inr >= client.max_spend_inr:
                stop = f"spend limit of INR {client.max_spend_inr:.2f} reached"
                break
    remaining = [rs.msg_id(n) for n in todo if rs.msg_id(n) not in saved]
    progress = {
        "updated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(todo),
        "done": len(todo) - len(remaining),
        "remaining": len(remaining),
        "stopped_because": stop,
        "next_message_id": remaining[0] if remaining else None,
    }
    PROGRESS.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    print(f"done {progress['done']} / {progress['total']}; remaining {progress['remaining']}")
    if stop:
        print("stopped:", stop)
    doc = public_summary(saved, len(todo))
    doc["complete"] = not remaining
    doc["remaining"] = len(remaining)
    text = json.dumps(doc, ensure_ascii=False)
    if "@" in text:
        raise RuntimeError("an '@' reached the public output; nothing was written")
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT.name, "(complete)" if doc["complete"] else "(INCOMPLETE)")
    if stop and "batch limit" in stop:
        return 0
    return 3 if stop else 0


if __name__ == "__main__":
    raise SystemExit(main())
