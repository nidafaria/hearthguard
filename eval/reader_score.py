"""Score the frozen Reader against the human labels. Run: python -m eval.reader_score

Refuses to compute (and says which rows) unless a person has filled in every label. If the Reader
has not been run on the test set yet, it runs it once (eval/reader_testrun.py) and then scores.

Unit of scoring: MESSAGE-LEVEL presence of each claim kind, because the sheet records yes/no per
message and kind, not spans. For a kind, a message is
  predicted  if the Reader returned at least one accepted claim of that kind for it, and
  labelled   if the person wrote "yes" for it.
Then per kind and for all kinds together (counts summed over the kinds):
  TP predicted and labelled     FP predicted, not labelled     FN labelled, not predicted
  precision = TP / (TP + FP)    recall = TP / (TP + FN)
Each rate is reported with its numerator and denominator and a 95% Wilson interval. Counts are
integers and are never rounded. A rate whose denominator is 0 is undefined and reported as null.

What this does not measure: whether an accepted claim's quote is the RIGHT text
(only that a claim of
that kind was returned for a message the person marked yes), and nothing about messages outside
this test set.
"""

import json
import math
import sys
from pathlib import Path

from eval import reader_freeze as rf
from eval import reader_sheet as sheet
from eval import reader_testrun as tr

RESULTS = Path(__file__).resolve().parent / "results"
SCORE_JSON = RESULTS / "reader_score.json"
SCORE_MD = RESULTS / "reader_score.md"
Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """95% Wilson score interval for k successes in n trials. None when n is 0."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(num: int, den: int) -> dict:
    ci = wilson(num, den)
    return {
        "numerator": num,
        "denominator": den,
        "value": None if den == 0 else num / den,
        "wilson95_low": None if ci is None else ci[0],
        "wilson95_high": None if ci is None else ci[1],
    }


def counts(labels: dict[str, dict[str, bool]], predicted: dict[str, set[str]], kind: str) -> dict:
    tp = fp = fn = tn = 0
    for mid, lab in labels.items():
        said, got = lab[kind], kind in predicted.get(mid, set())
        tp += said and got
        fp += got and not said
        fn += said and not got
        tn += (not said) and (not got)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def summarise(c: dict, n_messages: int) -> dict:
    return {
        **c,
        "messages": n_messages,
        "labelled_positives": c["tp"] + c["fn"],
        "predicted_positives": c["tp"] + c["fp"],
        "precision": rate(c["tp"], c["tp"] + c["fp"]),
        "recall": rate(c["tp"], c["tp"] + c["fn"]),
    }


def score(labels: dict[str, dict[str, bool]], predicted: dict[str, set[str]]) -> dict:
    per_kind = {k: counts(labels, predicted, k) for k in sheet.KINDS}
    n = len(labels)
    total = {key: sum(c[key] for c in per_kind.values()) for key in ("tp", "fp", "fn", "tn")}
    return {
        "per_kind": {k: summarise(c, n) for k, c in per_kind.items()},
        "all_kinds": summarise(total, n * len(sheet.KINDS)),
    }


def predicted_from_testrun(testrun: dict) -> dict[str, set[str]]:
    return {r["message_id"]: {c["kind"] for c in r["claims"]} for r in testrun["results"]}


# ----------------------------------------------------------------------------- the report
def _fmt_rate(r: dict, what: str) -> str:
    if r["denominator"] == 0:
        return f"undefined (0 {what})"
    return (
        f"{r['numerator']}/{r['denominator']} = {r['value']:.3f} "
        f"(95% Wilson {r['wilson95_low']:.3f} to {r['wilson95_high']:.3f}), "
        f"n = {r['denominator']} {what}"
    )


def markdown(result: dict, meta: dict) -> str:
    n = meta["messages"]
    lines = [
        "# Reader score on the hand-labelled test set",
        "",
        f"**The {n} messages are a test of this prompt only** (Reader freeze version "
        f"{meta['frozen_version']}), not of the Reader in general. "
        "Labels are by a person; nothing was "
        "inferred. Every line below states its sample size.",
        "",
        "**Unit:** message-level presence of each claim kind "
        "(the sheet records yes/no per message, "
        "not spans). A message is *predicted* for a kind if the Reader returned "
        "at least one accepted "
        "claim of that kind, and *labelled* if the person wrote yes. This does not check that the "
        "quote is the right text.",
        "",
        f"**Test set:** {n} messages. **Tokens used by the run:** {meta['tokens']}.",
        "",
        "| Kind | Precision | Recall |",
        "|---|---|---|",
    ]
    for kind, s in result["per_kind"].items():
        lines.append(
            f"| {kind} | {_fmt_rate(s['precision'], 'predicted positives')} "
            f"| {_fmt_rate(s['recall'], 'labelled positives')} |"
        )
    a = result["all_kinds"]
    lines += [
        f"| **All kinds together** (n = {a['messages']} message-kind pairs) "
        f"| {_fmt_rate(a['precision'], 'predicted positives')} "
        f"| {_fmt_rate(a['recall'], 'labelled positives')} |",
        "",
        f"Counts per kind (TP / FP / FN / TN, over {n} messages):",
        "",
    ]
    for kind, s in result["per_kind"].items():
        lines.append(
            f"- {kind}: {s['tp']} / {s['fp']} / {s['fn']} / {s['tn']} "
            f"(n = {s['messages']} messages)"
        )
    lines += [
        f"- All kinds: {a['tp']} / {a['fp']} / {a['fn']} / {a['tn']} "
        f"(n = {a['messages']} message-kind pairs)",
        "",
        "Read with care: a kind with few labelled or predicted positives has a very "
        "wide interval, and "
        "an undefined rate means there was nothing to divide by, not a score of zero or one.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    for needed, how in (
        (sheet.TESTSET_PATH, "make.ps1 reader-testset"),
        (sheet.SHEET_PATH, "make.ps1 reader-testset"),
    ):
        if not needed.exists():
            print(f"Not scoring: {needed.name} does not exist yet. Build the test set first: {how}")
            return 1
    frozen = rf.load_frozen()
    testset = json.loads(sheet.TESTSET_PATH.read_text(encoding="utf-8"))
    rows = sheet.read_sheet()
    check = sheet.check_labels(rows, testset)
    if not check.complete:
        print("Not scoring: the human labels are not complete. Rows to fix:")
        print("\n".join("  " + line for line in check.describe()))
        return 1
    if frozen is None or rf.mismatches(frozen):
        print("Not scoring: the Reader no longer matches its freeze.")
        return 1
    if not tr.TESTRUN_PATH.exists():
        code = tr.run()
        if code != 0:
            return code
    testrun = json.loads(tr.TESTRUN_PATH.read_text(encoding="utf-8"))
    if testrun["reader_frozen_components"] != frozen["components"]:
        print("Not scoring: the saved run was made with a different Reader than the frozen one.")
        return 1

    result = score(check.labels, predicted_from_testrun(testrun))
    t = testrun["totals"]
    meta = {
        "messages": len(check.labels),
        "frozen_version": frozen["version"],
        "tokens": f"{t['input_tokens']:,} input and {t['output_tokens']:,} output "
        f"({t['reasoning_tokens']:,} reasoning)",
    }
    doc = {
        "reader_frozen_version": frozen["version"],
        "labels_from": "a person; eval/results/reader_labelsheet.csv",
        "unit": "message-level presence per claim kind",
        "messages": len(check.labels),
        "counts_are_unrounded_integers": True,
        "confidence_interval": "Wilson score, 95%",
        **result,
    }
    SCORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    SCORE_MD.write_text(markdown(result, meta), encoding="utf-8")
    a = result["all_kinds"]
    print(f"scored {len(check.labels)} messages: all kinds TP {a['tp']} FP {a['fp']} FN {a['fn']}")
    print(f"precision {_fmt_rate(a['precision'], 'predicted positives')}")
    print(f"recall    {_fmt_rate(a['recall'], 'labelled positives')}")
    print(f"wrote {SCORE_JSON.name} and {SCORE_MD.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
