"""The test runner: when it refuses, when it runs, and that it runs once on the labelled text.

Uses the local HTTP stub in place of the model, so these test the runner's rules, not Groq.
"""

import csv
import json

import pytest

from core.claims import reader
from eval import reader_freeze as rf
from eval import reader_sheet as sheet
from eval import reader_testrun as tr
from tests.unit.llm_stub import CHAT, completion, make_client

TEXTS = {
    "msg00001": "Please hurry up with the release now.",
    "msg00002": "Nothing of interest in this note.",
    "msg00003": "I only have a few hours a month for this.",
}
HASHES = {mid: f"{i}" * 64 for i, mid in enumerate(TEXTS, start=1)}


def write_inputs(tmp_path, monkeypatch, labelled=True, texts=None):
    texts = texts or TEXTS
    testset = {
        "messages": [
            {"message_id": m, "author_hash": HASHES[m], "text_sha256": sheet.text_hash(t)}
            for m, t in texts.items()
        ]
    }
    (tmp_path / "testset.json").write_text(json.dumps(testset))
    with (tmp_path / "sheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sheet.COLUMNS)
        w.writeheader()
        for m, t in texts.items():
            row = {"message_id": m, "year": "2022", "cleaned_text": t, "notes": ""}
            row.update({k: ("no" if labelled else "") for k in sheet.KINDS})
            w.writerow(row)
    monkeypatch.setattr(sheet, "TESTSET_PATH", tmp_path / "testset.json")
    monkeypatch.setattr(sheet, "SHEET_PATH", tmp_path / "sheet.csv")
    monkeypatch.setattr(tr, "TESTRUN_PATH", tmp_path / "testrun.json")


REPLY = '{"claims": [{"kind": "PRESSURE", "quote": "hurry up", "confidence": 0.8}]}'


def test_it_refuses_to_run_before_the_labels_are_done_and_makes_no_call(
    site, tmp_path, monkeypatch, capsys
):
    write_inputs(tmp_path, monkeypatch, labelled=False)
    site.routes[CHAT] = completion(REPLY)
    assert tr.run(client=make_client(site, tmp_path)) == 1
    out = capsys.readouterr().out
    assert "NOT been run" in out and "msg00001: no label in" in out
    assert site.posts == [] and not (tmp_path / "testrun.json").exists()


def test_it_refuses_to_run_if_the_reader_changed_after_the_freeze(site, tmp_path, monkeypatch):
    write_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(reader, "SYSTEM_PROMPT", reader.SYSTEM_PROMPT + " Changed.")
    assert tr.run(client=make_client(site, tmp_path)) == 1
    assert site.posts == []


def test_it_refuses_if_a_labelled_text_was_edited(site, tmp_path, monkeypatch):
    write_inputs(tmp_path, monkeypatch)
    rows = sheet.read_sheet()
    rows[0]["cleaned_text"] = "A different text from the one that was labelled."
    with (tmp_path / "sheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sheet.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    assert tr.run(client=make_client(site, tmp_path)) == 1
    assert site.posts == []


def test_it_stops_before_any_call_when_the_projected_cost_is_over_the_cap(
    site, tmp_path, monkeypatch, capsys
):
    write_inputs(tmp_path, monkeypatch)
    site.routes[CHAT] = completion(REPLY)
    code = tr.run(cap=100, client=make_client(site, tmp_path))
    assert code == 5 and site.posts == []
    out = capsys.readouterr().out
    assert "Stopped before any call" in out and "over the 100 cap" in out


def test_the_default_cap_is_60000_and_can_be_changed_on_purpose(monkeypatch):
    monkeypatch.delenv("READER_TOKEN_CAP", raising=False)
    assert tr.token_cap(None) == 60_000
    assert tr.token_cap(90_000) == 90_000
    monkeypatch.setenv("READER_TOKEN_CAP", "75000")
    assert tr.token_cap(None) == 75_000


def test_the_projection_comes_from_the_measured_spot_check():
    per_message = tr.tokens_per_message_measured()
    assert 500 < per_message < 5000
    assert tr.projected_tokens(60) == pytest.approx(per_message * 60, abs=1)


def test_it_runs_once_on_the_sheet_text_with_the_recorded_author_hash(site, tmp_path, monkeypatch):
    write_inputs(tmp_path, monkeypatch)
    site.routes[CHAT] = completion(REPLY, prompt_tokens=100, completion_tokens=40, reasoning=30)
    assert tr.run(cap=10_000, client=make_client(site, tmp_path)) == 0
    assert len(site.posts) == 3
    sent = [p["messages"][1]["content"] for p in site.posts]
    for (mid, text), body in zip(TEXTS.items(), sent, strict=True):
        assert text in body and HASHES[mid] in body  # the labelled text and the recorded hash

    doc = json.loads((tmp_path / "testrun.json").read_text(encoding="utf-8"))
    frozen = rf.load_frozen()
    assert doc["reader_frozen_version"] == frozen["version"]
    assert doc["reader_frozen_components"] == frozen["components"]
    assert doc["messages"] == 3 and doc["token_cap_used"] == 10_000
    assert doc["totals"]["input_tokens"] == 300 and doc["totals"]["output_tokens"] == 120
    first = doc["results"][0]
    assert first["message_id"] == "msg00001"
    assert [c["quote"] for c in first["claims"]] == ["hurry up"]
    assert first["claims"][0]["offset"] == TEXTS["msg00001"].index("hurry up")

    # A second call does not run the model again and does not overwrite the saved run.
    before = (tmp_path / "testrun.json").read_text(encoding="utf-8")
    assert tr.run(cap=10_000, client=make_client(site, tmp_path)) == 0
    assert (
        len(site.posts) == 3 and (tmp_path / "testrun.json").read_text(encoding="utf-8") == before
    )


def test_an_invented_quote_is_rejected_and_never_counted_as_a_claim(site, tmp_path, monkeypatch):
    write_inputs(tmp_path, monkeypatch)
    invented = (
        '{"claims": [{"kind": "VOUCH", "quote": "trust this person fully", "confidence": 0.9}]}'
    )
    site.routes[CHAT] = completion(invented)
    assert tr.run(cap=10_000, client=make_client(site, tmp_path)) == 0
    doc = json.loads((tmp_path / "testrun.json").read_text(encoding="utf-8"))
    assert doc["totals"]["claims"] == 0 and doc["totals"]["rejections"] == 3


def test_it_stops_if_the_real_cost_runs_past_the_cap(site, tmp_path, monkeypatch):
    write_inputs(tmp_path, monkeypatch)
    # The projection (about 4,556) fits under a 5,000 cap, but each reply really costs 2,000,
    # so the running total passes 5,000 on the third message.
    site.routes[CHAT] = completion(REPLY, prompt_tokens=1_000, completion_tokens=1_000)
    with pytest.raises(tr.TokenCapExceeded, match="over the 5000 cap"):
        tr.run(cap=5_000, client=make_client(site, tmp_path))
    assert not (tmp_path / "testrun.json").exists()  # a stopped run saves nothing as a result
