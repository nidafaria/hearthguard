"""The scorer against counts worked out by hand, and the label checks that guard it."""

import json

import pytest

from eval import reader_score as sc
from eval import reader_sheet as sheet

KINDS = sheet.KINDS


# ------------------------------------------------------------------ the 10-row example
# Ten messages m1..m10. "Labelled" is what the person said yes to; "predicted" is what the Reader
# returned. Worked out by hand, per kind:
#
#   PRESSURE   labelled m1 m2 m3 m4      predicted m1 m2 m5
#              TP = {m1, m2} = 2   FP = {m5} = 1   FN = {m3, m4} = 2   TN = 10 - 2 - 1 - 2 = 5
#              precision 2/3, recall 2/4
#   VOUCH      labelled m5 m6           predicted m5 m6 m8
#              TP = {m5, m6} = 2   FP = {m8} = 1   FN = 0              TN = 10 - 2 - 1 - 0 = 7
#              precision 2/3, recall 2/2
#   CAPACITY   labelled m7              predicted nothing
#              TP = 0   FP = 0   FN = {m7} = 1   TN = 10 - 0 - 0 - 1 = 9
#              precision 0/0 (undefined), recall 0/1
#   the other four kinds: nothing labelled, nothing predicted: TP = FP = FN = 0, TN = 10
#
#   All kinds together (sum over the seven kinds, 70 message-kind pairs):
#     TP = 2 + 2 + 0 = 4   FP = 1 + 1 + 0 = 2   FN = 2 + 0 + 1 = 3   TN = 70 - 4 - 2 - 3 = 61
#              precision 4/6, recall 4/7
def example():
    ids = [f"m{i}" for i in range(1, 11)]
    yes = {
        "PRESSURE": {"m1", "m2", "m3", "m4"},
        "VOUCH": {"m5", "m6"},
        "CAPACITY_STATEMENT": {"m7"},
    }
    labels = {m: {k: m in yes.get(k, set()) for k in KINDS} for m in ids}
    predicted = {
        "m1": {"PRESSURE"},
        "m2": {"PRESSURE"},
        "m5": {"PRESSURE", "VOUCH"},
        "m6": {"VOUCH"},
        "m8": {"VOUCH"},
    }
    return labels, predicted


def test_the_ten_row_example_gives_the_hand_computed_counts():
    result = sc.score(*example())
    pk = result["per_kind"]
    assert (
        pk["PRESSURE"]["tp"],
        pk["PRESSURE"]["fp"],
        pk["PRESSURE"]["fn"],
        pk["PRESSURE"]["tn"],
    ) == (2, 1, 2, 5)
    assert (pk["VOUCH"]["tp"], pk["VOUCH"]["fp"], pk["VOUCH"]["fn"], pk["VOUCH"]["tn"]) == (
        2,
        1,
        0,
        7,
    )
    cap = pk["CAPACITY_STATEMENT"]
    assert (cap["tp"], cap["fp"], cap["fn"], cap["tn"]) == (0, 0, 1, 9)
    for quiet in ("URGENCY", "REQUESTS_PRIVILEGE", "CHANGE_REQUEST", "HANDOVER_ANNOUNCEMENT"):
        assert (pk[quiet]["tp"], pk[quiet]["fp"], pk[quiet]["fn"], pk[quiet]["tn"]) == (0, 0, 0, 10)
    a = result["all_kinds"]
    assert (a["tp"], a["fp"], a["fn"], a["tn"]) == (4, 2, 3, 61)
    assert a["messages"] == 70 and a["tp"] + a["fp"] + a["fn"] + a["tn"] == 70


def test_the_rates_carry_their_numerators_and_denominators():
    pk = sc.score(*example())["per_kind"]
    p, r = pk["PRESSURE"]["precision"], pk["PRESSURE"]["recall"]
    assert (p["numerator"], p["denominator"]) == (2, 3) and p["value"] == pytest.approx(2 / 3)
    assert (r["numerator"], r["denominator"]) == (2, 4) and r["value"] == 0.5
    assert pk["VOUCH"]["recall"]["value"] == 1.0
    a = sc.score(*example())["all_kinds"]
    assert (a["precision"]["numerator"], a["precision"]["denominator"]) == (4, 6)
    assert (a["recall"]["numerator"], a["recall"]["denominator"]) == (4, 7)


def test_a_rate_with_nothing_to_divide_by_is_undefined_not_zero():
    cap = sc.score(*example())["per_kind"]["CAPACITY_STATEMENT"]
    assert cap["precision"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
        "wilson95_low": None,
        "wilson95_high": None,
    }
    assert cap["recall"]["value"] == 0.0 and cap["recall"]["denominator"] == 1
    assert cap["labelled_positives"] == 1 and cap["predicted_positives"] == 0


def test_counts_are_integers_and_never_rounded():
    result = sc.score(*example())
    for s in [*result["per_kind"].values(), result["all_kinds"]]:
        for key in (
            "tp",
            "fp",
            "fn",
            "tn",
            "messages",
            "labelled_positives",
            "predicted_positives",
        ):
            assert type(s[key]) is int


# ------------------------------------------------------------------ the Wilson interval
def test_wilson_matches_published_values():
    low, high = sc.wilson(8, 10)
    assert (low, high) == (pytest.approx(0.4902, abs=1e-3), pytest.approx(0.9433, abs=1e-3))
    low, high = sc.wilson(0, 10)
    assert low == 0.0 and high == pytest.approx(0.2775, abs=1e-3)
    low, high = sc.wilson(10, 10)
    assert low == pytest.approx(0.7225, abs=1e-3) and high == pytest.approx(1.0)


def test_wilson_is_symmetric_and_nested_and_undefined_for_no_trials():
    low, high = sc.wilson(2, 7)
    low2, high2 = sc.wilson(5, 7)
    assert low == pytest.approx(1 - high2) and high == pytest.approx(1 - low2)
    assert 0 <= low <= 2 / 7 <= high <= 1
    assert sc.wilson(0, 0) is None
    narrow, wide = sc.wilson(50, 100), sc.wilson(5, 10)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]  # more data, narrower interval


# ------------------------------------------------------------------ the report
def test_every_line_of_the_report_states_its_sample_size_and_the_prompt_only_warning():
    meta = {"messages": 10, "frozen_version": 1, "tokens": "1 input and 1 output (0 reasoning)"}
    md = sc.markdown(sc.score(*example()), meta)
    assert "test of this prompt only" in md and "version 1" in md
    table = [ln for ln in md.splitlines() if ln.startswith("| ") and "---" not in ln][1:]
    assert len(table) == len(KINDS) + 1
    for ln in table:
        assert ln.count("n =") >= 1 or "undefined" in ln
    for ln in md.splitlines():
        if ln.startswith("- "):
            assert "(n = " in ln
    assert "undefined (0 predicted positives)" in md


def test_predictions_come_from_the_accepted_claims_of_the_saved_run():
    run = {
        "results": [
            {
                "message_id": "a",
                "claims": [{"kind": "PRESSURE"}, {"kind": "PRESSURE"}, {"kind": "VOUCH"}],
            },
            {"message_id": "b", "claims": []},
        ]
    }
    assert sc.predicted_from_testrun(run) == {"a": {"PRESSURE", "VOUCH"}, "b": set()}


# ------------------------------------------------------------------ checking the human labels
def make_testset(ids, texts=None):
    texts = texts or {i: f"text of {i}" for i in ids}
    return {"messages": [{"message_id": i, "text_sha256": sheet.text_hash(texts[i])} for i in ids]}


def row(mid, text=None, **labels):
    base = {
        "message_id": mid,
        "year": "2022",
        "cleaned_text": text or f"text of {mid}",
        "notes": "",
    }
    base.update({k: "no" for k in KINDS})
    base.update(labels)
    return base


def test_a_fully_labelled_sheet_is_complete_and_parsed():
    check = sheet.check_labels([row("a", PRESSURE="YES"), row("b")], make_testset(["a", "b"]))
    assert (
        check.complete
        and check.labels["a"]["PRESSURE"] is True
        and check.labels["b"]["PRESSURE"] is False
    )


def test_an_empty_label_blocks_scoring_and_names_the_row_and_column():
    check = sheet.check_labels([row("a", VOUCH=""), row("b")], make_testset(["a", "b"]))
    assert not check.complete and check.missing == [("a", ["VOUCH"])]
    assert "a: no label in VOUCH" in check.describe()
    assert "a" not in check.labels  # a half-labelled row is never used


def test_anything_but_yes_or_no_is_invalid():
    check = sheet.check_labels([row("a", URGENCY="maybe")], make_testset(["a"]))
    assert not check.complete and check.invalid == [("a", "URGENCY", "maybe")]


def test_a_missing_or_extra_row_blocks_scoring():
    check = sheet.check_labels([row("a"), row("z")], make_testset(["a", "b"]))
    assert check.absent_ids == ["b"] and check.unexpected_ids == ["z"] and not check.complete


def test_changed_text_is_detected_but_line_ending_changes_are_not():
    ts = make_testset(["a"], {"a": "line one\nline two"})
    crlf = sheet.check_labels([row("a", text="line one\r\nline two\r\n")], ts)
    assert crlf.complete  # a spreadsheet program may rewrite line endings
    edited = sheet.check_labels([row("a", text="line one\nline TWO")], ts)
    assert edited.edited_text_ids == ["a"] and not edited.complete


def test_a_sheet_missing_a_column_is_reported():
    bad = row("a")
    del bad["VOUCH"]
    check = sheet.check_labels([bad], make_testset(["a"]))
    assert check.missing_columns == ["VOUCH"] and not check.complete


# ------------------------------------------------------------------ main(): refuse or score
def write_sheet(path, rows):
    import csv

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sheet.COLUMNS)
        w.writeheader()
        w.writerows(rows)


def setup_files(tmp_path, monkeypatch, rows, predicted):
    ids = [r["message_id"] for r in rows]
    testset = tmp_path / "testset.json"
    testset.write_text(
        json.dumps(make_testset(ids, {r["message_id"]: r["cleaned_text"] for r in rows}))
    )
    sheet_path = tmp_path / "sheet.csv"
    write_sheet(sheet_path, rows)
    run = tmp_path / "run.json"
    frozen = sc.rf.load_frozen()
    run.write_text(
        json.dumps(
            {
                "reader_frozen_components": frozen["components"],
                "totals": {"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 3},
                "results": [
                    {"message_id": i, "claims": [{"kind": k} for k in predicted.get(i, [])]}
                    for i in ids
                ],
            }
        )
    )
    monkeypatch.setattr(sheet, "SHEET_PATH", sheet_path)
    monkeypatch.setattr(sheet, "TESTSET_PATH", testset)
    monkeypatch.setattr(sc.tr, "TESTRUN_PATH", run)
    monkeypatch.setattr(sc, "SCORE_JSON", tmp_path / "score.json")
    monkeypatch.setattr(sc, "SCORE_MD", tmp_path / "score.md")
    return tmp_path


def test_main_refuses_when_a_label_is_missing_and_writes_nothing(tmp_path, monkeypatch, capsys):
    rows = [row("a", PRESSURE="yes"), row("b", VOUCH="")]
    setup_files(tmp_path, monkeypatch, rows, {"a": ["PRESSURE"]})
    assert sc.main() == 1
    out = capsys.readouterr().out
    assert "b: no label in VOUCH" in out and "Not scoring" in out
    assert not (tmp_path / "score.json").exists() and not (tmp_path / "score.md").exists()


def test_main_scores_a_complete_sheet_and_writes_both_files(tmp_path, monkeypatch):
    rows = [row("a", PRESSURE="yes"), row("b", PRESSURE="yes"), row("c")]
    setup_files(tmp_path, monkeypatch, rows, {"a": ["PRESSURE"], "c": ["PRESSURE"]})
    assert sc.main() == 0
    doc = json.loads((tmp_path / "score.json").read_text())
    p = doc["per_kind"]["PRESSURE"]
    # a is TP, b is FN, c is FP: precision 1/2, recall 1/2
    assert (p["tp"], p["fp"], p["fn"], p["tn"]) == (1, 1, 1, 0)
    assert (p["precision"]["numerator"], p["precision"]["denominator"]) == (1, 2)
    assert (
        doc["messages"] == 3 and "test of this prompt only" in (tmp_path / "score.md").read_text()
    )


def test_main_says_what_to_do_when_there_is_no_test_set_yet(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sheet, "TESTSET_PATH", tmp_path / "missing_testset.json")
    monkeypatch.setattr(sheet, "SHEET_PATH", tmp_path / "missing_sheet.csv")
    assert sc.main() == 1
    assert "does not exist yet" in capsys.readouterr().out
