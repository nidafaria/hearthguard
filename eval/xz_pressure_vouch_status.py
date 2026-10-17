"""Pressure and Vouch on org_xz at each quarter-end 2021-Q4 to 2024-Q1, from real Reader output.

Run: python -m eval.xz_pressure_vouch_status
Needs the Reader run (python -m eval.reader_full_run) and a running FalkorDB.

Steps: write the Reader's accepted claims into org_xz (idempotent MERGE; see
core/claims/graph_write.py and docs/decisions/0004-mail-claims-in-org-xz.md), then run both
detectors per quarter. Writes eval/results/pressure_vouch_status.json: per quarter and detector
the status, the reason, the evidence counts and the queries with their times. It holds hashed
ids nowhere (query parameters that carry them are replaced) and no message text.

The coverage block says how many of the in-scope messages the Reader has read. If the Reader run
is not finished, a quarter's result covers only the messages read so far, and the file says so.
Vouch uses SHARES edges; none are built (creation windows of the mail posters are not in the
public record we hold), so Vouch can only be NOT_FIRED or NOT_COMPUTED here.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.claims import graph_write
from core.detectors import pressure, vouch
from core.detectors.low_history import thresholds
from core.graph.client import FalkorClient
from eval import reader_full_run as rfr
from packs.oss import mail_cache

RESULTS = Path(__file__).resolve().parent / "results"
OUT = RESULTS / "pressure_vouch_status.json"
NORMAL = RESULTS / "xz_normal.json"
ORG = "xz"
REDACTED = "<hashed id, not written>"


def quarters() -> list[dict]:
    doc = json.loads(NORMAL.read_text(encoding="utf-8"))
    return [{"quarter": r["quarter"], "T": r["T"], "T_iso": r["T_iso"]} for r in doc["results"]]


def _redact(queries: list[dict]) -> list[dict]:
    out = []
    for q in queries:
        params = {k: (REDACTED if k in ("hid", "hids") else v) for k, v in q["params"].items()}
        out.append({**q, "params": params})
    return out


def is_read(saved: dict, key: str) -> bool:
    """Read by the Reader. A message too long for one request was recorded but not read."""
    return key in saved and saved[key]["skipped"] not in (rfr.TOO_LONG, rfr.NO_VALID_JSON)


def coverage() -> dict:
    todo = [n for n in rfr.in_scope_ids() if n not in rfr.excluded_ids()]
    saved = rfr.load_saved()
    done = sum(1 for n in todo if f"msg{n:05d}" in saved)
    return {
        "in_scope_messages": len(rfr.in_scope_ids()),
        "excluded_human_labelled_test_set": len(rfr.excluded_ids()),
        "to_read": len(todo),
        "read_so_far": done,
        "complete": done == len(todo),
        "recorded_but_not_read": sum(
            1 for n in todo if f"msg{n:05d}" in saved and not is_read(saved, f"msg{n:05d}")
        ),
    }


def window_coverage(T: int, window_days: int | None, saved: dict) -> dict:
    """How many in-scope messages dated in the detector's window the Reader has read.

    A message not read (held out for the labelled test set, or the run is unfinished) could hold
    a claim, so a NOT_FIRED over a window with unread messages is only a result on the read ones.
    """
    start = None if window_days is None else T - window_days * 86400
    total = read = 0
    for r in mail_cache.build_index():
        if r["status"] != 200 or not r["in_scope"] or not r["date_utc"]:
            continue
        at = graph_write.to_epoch(r["date_utc"])
        if at > T or (start is not None and at <= start):
            continue
        total += 1
        read += is_read(saved, f"msg{r['msg']:05d}")
    return {"messages_in_window": total, "read": read, "unread": total - read}


def build(client: FalkorClient) -> dict:
    cov = coverage()
    saved = rfr.load_saved()
    written = graph_write.write_claims(client, f"org_{ORG}", list(rfr.load_saved().values()))
    pressure_days = thresholds()["pressure"]["window_days"]
    out = []
    for q in quarters():
        row = {**q}
        row["window_coverage"] = {
            "pressure": window_coverage(q["T"], pressure_days, saved),
            "vouch": window_coverage(q["T"], None, saved),
        }
        for name, fn in (("pressure", pressure.pressure), ("vouch", vouch.vouch)):
            res = fn(client, ORG, q["T"])
            row[name] = {
                "status": res.status,
                "reason": res.reason,
                "evidence": res.evidence,
                "query_ms": res.query_ms,
                "queries": _redact(res.queries),
            }
        out.append(row)
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "org": ORG,
        "reader_frozen_version": 1,
        "coverage": cov,
        "claims_written_to_graph": written,
        "provisional": True,
        "quarters": out,
        "not_computed_notes": {
            "pressure": "Condition 2 (keeper activity <= 50% of the org's trailing-two-year "
            "median, or a keeper CAPACITY_STATEMENT) is open in the freeze, so Pressure can "
            "only be NOT_FIRED (condition 1 fails) or NOT_COMPUTED (condition 1 holds).",
            "vouch": "The Reader does not extract the candidate (target), and no SHARES edge "
            "can be built from the public record we hold, so Vouch can only be NOT_FIRED or "
            "NOT_COMPUTED.",
        },
    }


def main() -> int:
    doc = build(FalkorClient())
    text = json.dumps(doc, indent=2)
    if "@" in text:
        raise RuntimeError("an '@' reached the output; nothing was written")
    OUT.write_text(text + "\n", encoding="utf-8")
    cov = doc["coverage"]
    print(f"coverage: {cov['read_so_far']} / {cov['to_read']} messages read")
    for r in doc["quarters"]:
        print(f"{r['quarter']}: pressure {r['pressure']['status']}, vouch {r['vouch']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
