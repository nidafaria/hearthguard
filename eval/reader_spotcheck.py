"""Run the Reader on a fixed sample of 20 xz-devel messages and record what it returned.

Run:  python -m eval.reader_spotcheck            run the 20 messages (live Groq, cached)
      python -m eval.reader_spotcheck show 407   print one cleaned message and its claims, for the
                                                 hand-check (names and emails are already removed)

Sample rule (no hand-picking): take the 300 in-scope messages (msg00397 to msg00696), and every
15th one, with the grid anchored so that msg00512 is on it. That gives exactly 20: msg00407,
msg00422, ... msg00692. (Stepping 15 upward from msg00512 alone cannot give 20: the archive ends
at msg00708, so that would stop at 14.)

Writes eval/results/reader_sample.json and eval/results/reader_spotcheck.json. The second holds
quotes of at most 25 words, offsets, kinds, confidences, counts and token totals. It holds no
email, no full message body and no name except the public persona "Jia Tan".

Stops, writing nothing, if the run would pass 50,000 tokens in total.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

from core.claims import reader
from core.llm.client import LLMClient, load_config
from packs.oss import mail_cache

RESULTS = Path(__file__).resolve().parent / "results"
SAMPLE_PATH = RESULTS / "reader_sample.json"
OUT_PATH = RESULTS / "reader_spotcheck.json"
ANCHOR, STEP = 512, 15
TOKEN_BUDGET = 50_000  # stop if the 20 messages would use more than this in total
PROJECT_AFTER = 3  # after this many fresh calls, project the total and stop if it is over budget


class BudgetExceeded(RuntimeError):
    pass


def msg_id(n: int) -> str:
    return f"msg{n:05d}"


def select_sample(root: Path = mail_cache.RAW_ROOT) -> list[int]:
    rows = mail_cache.build_index(root)
    in_scope = sorted(r["msg"] for r in rows if r["status"] == 200 and r["in_scope"])
    sample = [m for m in in_scope if (m - ANCHOR) % STEP == 0]
    if len(sample) != 20:
        raise RuntimeError(f"the sampling rule gave {len(sample)} messages, not 20")
    return sample


def load_page(n: int, root: Path = mail_cache.RAW_ROOT) -> str:
    return (root / mail_cache.msg_name(n)).read_text(encoding="utf-8", errors="replace")


def build_redactor(root: Path = mail_cache.RAW_ROOT) -> reader.Redactor:
    names, bodies = set(), []
    for page_path in sorted(root.glob("msg*.html")):
        page = page_path.read_text(encoding="utf-8", errors="replace")
        sender = mail_cache.parse_message(page)["sender_name"]
        if sender:
            names.add(sender)
        try:
            bodies.append(reader.body_text(page))
        except ValueError:
            continue
    return reader.Redactor.from_names(names, reader.lowercase_vocabulary(bodies))


def prepare(n: int, redactor: reader.Redactor, root: Path = mail_cache.RAW_ROOT):
    page = load_page(n, root)
    head = mail_cache.parse_message(page)
    author_hash, _ = mail_cache.author_hash(head["sender_email"], head["sender_name"])
    clean = reader.clean_message(page, redactor, head["sender_name"])
    return head, author_hash, clean


def run() -> int:
    config = load_config()
    client = LLMClient(config)
    if not client.has_key:
        print("GROQ_API_KEY is not set (add it to .env)")
        return 2
    sample = select_sample()
    RESULTS.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.write_text(
        json.dumps(
            {
                "rule": (
                    "every 15th of the 300 in-scope xz-devel messages (msg00397 to msg00696), "
                    "grid anchored so that msg00512 is on it; no hand-picking"
                ),
                "anchor": msg_id(ANCHOR),
                "step": STEP,
                "count": len(sample),
                "ids": [msg_id(n) for n in sample],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    redactor = build_redactor()
    entries, fresh_tokens, fresh_calls = [], 0, 0
    for i, n in enumerate(sample, start=1):
        head, author_hash, clean = prepare(n, redactor)
        res = reader.read_message(clean.text, author_hash, client=client)
        rec = res.record
        used = 0 if rec is None else rec.input_tokens + rec.output_tokens
        if rec is not None and not rec.cache_hit:
            fresh_tokens += used
            fresh_calls += 1
        _guard(fresh_tokens, fresh_calls, len(sample), i)
        entries.append(_entry(n, head, author_hash, clean, res))
        print(
            f"{msg_id(n)}: {len(res.claims)} claims, {len(res.rejections)} rejected, {used} tokens"
        )

    doc = {
        "what": (
            "Spot check of the Reader on 20 messages. Not a precision or recall claim. "
            "Quotes are exact substrings of the cleaned text the model saw."
        ),
        "model": config["extraction_model"],
        "sample_file": "eval/results/reader_sample.json",
        "totals": _totals(entries),
        "messages": entries,
    }
    _assert_no_names_or_emails(doc, redactor)
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    t = doc["totals"]
    print(
        f"\n{t['messages']} messages | claims {t['claims']} | rejected {t['rejections']} | "
        f"tokens in/out/reasoning "
        f"{t['input_tokens']}/{t['output_tokens']}/{t['reasoning_tokens']} | "
        f"cache hits {t['cache_hits']}"
    )
    return 0


def _guard(fresh_tokens: int, fresh_calls: int, total: int, done: int) -> None:
    if fresh_tokens > TOKEN_BUDGET:
        raise BudgetExceeded(f"{fresh_tokens} tokens used, over the {TOKEN_BUDGET} budget; stopped")
    if fresh_calls == PROJECT_AFTER and done < total:
        projected = fresh_tokens / fresh_calls * total
        if projected > TOKEN_BUDGET:
            raise BudgetExceeded(
                f"{fresh_calls} calls used {fresh_tokens} tokens; the {total} messages would use "
                f"about {projected:.0f}, over the {TOKEN_BUDGET} budget; stopped"
            )


def _entry(n, head, author_hash, clean, res: reader.ReadResult) -> dict:
    rec = res.record
    return {
        "message_id": msg_id(n),
        "date_utc": head["date"].isoformat().replace("+00:00", "Z") if head["date"] else None,
        "author_hash": author_hash,
        "text_chars": len(clean.text),
        "text_sha256": hashlib.sha256(clean.text.encode("utf-8")).hexdigest(),
        "emails_replaced": clean.emails_replaced,
        "names_replaced": clean.names_replaced,
        "claim_count": len(res.claims),
        "claims": [
            {
                "kind": c.kind,
                "quote": c.quote,
                "offset": c.offset,
                "confidence": c.confidence,
                "occurrences": c.occurrences,
            }
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
        "latency_ms": None if rec is None else round(rec.latency_ms),
        "attempts": None if rec is None else rec.attempts,
    }


def _totals(entries: list[dict]) -> dict:
    tok = [e["tokens"] for e in entries if e["tokens"]]
    return {
        "messages": len(entries),
        "claims": sum(e["claim_count"] for e in entries),
        "rejections": sum(e["rejection_count"] for e in entries),
        "none_items": sum(e["none_items"] for e in entries),
        "messages_without_claims": sum(1 for e in entries if e["claim_count"] == 0),
        "input_tokens": sum(t["input"] for t in tok),
        "output_tokens": sum(t["output"] for t in tok),
        "reasoning_tokens": sum(t["reasoning"] or 0 for t in tok),
        "cache_hits": sum(1 for e in entries if e["cache_hit"]),
        "claims_by_kind": _count(c["kind"] for e in entries for c in e["claims"]),
        "rejections_by_reason": _count(r["reason"] for e in entries for r in e["rejections"]),
    }


def _count(items) -> dict:
    out: dict = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return dict(sorted(out.items()))


def _assert_no_names_or_emails(doc: dict, redactor: reader.Redactor) -> None:
    text = json.dumps(doc, ensure_ascii=False)
    if "@" in text:
        raise RuntimeError("an '@' reached the output; nothing was written")
    for name in [*redactor.full_names, *redactor.tokens]:
        if re.search(rf"\b{re.escape(name)}\b", text):
            raise RuntimeError("a known sender name reached the output; nothing was written")


def show(n: int) -> int:
    redactor = build_redactor()
    head, author_hash, clean = prepare(n, redactor)
    res = reader.read_message(clean.text, author_hash, client=LLMClient())
    print(
        f"##### {msg_id(n)} | {len(clean.text)} chars | {len(res.claims)} claims | "
        f"{len(res.rejections)} rejected"
    )
    print(clean.text)
    for c in res.claims:
        print(f"  CLAIM {c.kind} conf={c.confidence} @byte {c.offset}: {c.quote!r}")
    for r in res.rejections:
        print(f"  REJECTED {r.kind}: {r.reason}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "show":
        sys.exit(show(int(sys.argv[2])))
    sys.exit(run())
