"""The Reader freeze: the committed freeze matches the code, and changes are caught and logged."""

import json

import pytest

from core.claims import reader
from eval import reader_freeze as rf


def test_the_committed_freeze_matches_the_prompt_and_config_as_they_are():
    # If this fails, the Reader prompt, schema, parameters or config/models.yaml changed after the
    # freeze. That makes the labelled test invalid: log it with `--new-version --reason "..."`.
    frozen = rf.load_frozen()
    assert frozen is not None, "run `python -m eval.reader_freeze` to freeze the Reader first"
    assert rf.mismatches(frozen) == []


def test_the_freeze_records_a_hash_for_each_component_and_a_timestamp():
    frozen = rf.load_frozen()
    assert set(frozen["components"]) == set(rf.FROZEN_COMPONENTS)
    assert all(len(h) == 64 for h in frozen["components"].values())
    assert frozen["frozen_at_utc"].endswith("Z") and frozen["version"] >= 1
    assert frozen["parameters"]["model"] == "openai/gpt-oss-20b"
    assert frozen["parameters"]["temperature"] == 0


def test_the_hashes_are_stable_between_calls():
    assert rf.current_components() == rf.current_components()


def test_editing_the_system_prompt_is_caught_as_that_component_only(monkeypatch, tmp_path):
    frozen = rf.create(tmp_path / "frozen.json")
    assert rf.mismatches(frozen) == []
    monkeypatch.setattr(reader, "SYSTEM_PROMPT", reader.SYSTEM_PROMPT + " Be creative.")
    assert rf.mismatches(frozen) == ["system_prompt_sha256"]


def test_editing_the_models_file_is_caught(monkeypatch, tmp_path):
    frozen = rf.create(tmp_path / "frozen.json")
    copy = tmp_path / "models.yaml"
    copy.write_text(rf.MODELS_YAML.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    monkeypatch.setattr(rf, "MODELS_YAML", copy)
    assert "models_yaml_sha256" in rf.mismatches(frozen)


def test_changing_a_call_parameter_is_caught(monkeypatch, tmp_path):
    frozen = rf.create(tmp_path / "frozen.json")
    monkeypatch.setattr(reader, "MAX_TOKENS", 999)
    assert "parameters_sha256" in rf.mismatches(frozen)


def test_a_new_version_keeps_the_old_one_with_its_reason_and_whether_labels_existed(tmp_path):
    path = tmp_path / "frozen.json"
    v1 = rf.create(path)
    v2 = rf.new_version("tightened the prompt", path, labels=True)
    assert (v1["version"], v2["version"]) == (1, 2)
    assert len(v2["history"]) == 1
    old = v2["history"][0]
    assert old["version"] == 1 and old["retired_because"] == "tightened the prompt"
    assert old["labels_existed_when_retired"] is True and old["retired_at_utc"].endswith("Z")
    assert old["components"] == v1["components"]
    again = rf.new_version("second change", path, labels=False)
    assert again["version"] == 3 and [h["version"] for h in again["history"]] == [1, 2]
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 3


def test_a_new_version_needs_a_reason_and_something_to_replace(tmp_path):
    with pytest.raises(ValueError, match="nothing is frozen"):
        rf.new_version("because", tmp_path / "missing.json")
    path = tmp_path / "frozen.json"
    rf.create(path)
    with pytest.raises(ValueError, match="needs a reason"):
        rf.new_version("   ", path)


def test_the_label_columns_are_the_seven_claim_kinds():
    assert rf.reader_kinds() == [
        "PRESSURE",
        "URGENCY",
        "VOUCH",
        "REQUESTS_PRIVILEGE",
        "CAPACITY_STATEMENT",
        "CHANGE_REQUEST",
        "HANDOVER_ANNOUNCEMENT",
    ]
