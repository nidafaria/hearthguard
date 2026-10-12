"""Synthetic tallowdate case: deterministic generator, every entity labelled synthetic."""

import json

from redteam.tallowdate import (
    CASE,
    MIRA,
    REVIEW_COUNT,
    ROWAN,
    TOMAS,
    build_case,
    write_case,
)

ALLOWED_PEOPLE = {MIRA, TOMAS, ROWAN}
ALLOWED_ACTORS = ALLOWED_PEOPLE | {"acct-a", "acct-b", "acct-c"}


def test_two_runs_write_identical_files(tmp_path):
    first = write_case(tmp_path / "first.json")
    second = write_case(tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()


def test_every_entity_is_synthetic_and_only_fictional_names_appear():
    case = build_case()
    assert case["synthetic"] is True
    assert case["case"] == CASE

    for person in case["people"]:
        assert person["synthetic"] is True
        assert person["name"] in ALLOWED_PEOPLE

    assert case["events"], "generator wrote no events"
    for event in case["events"]:
        assert event["synthetic"] is True, event["id"]
        assert event["actor"] in ALLOWED_ACTORS, event["id"]
        assert event["campaign_id"] is None or event["planted"] is True, event["id"]


def test_written_file_matches_the_built_case(tmp_path):
    path = write_case(tmp_path / "case.json")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(build_case(), ensure_ascii=False))


def test_events_are_in_date_order_with_background_reviews_counted():
    events = build_case()["events"]
    dates = [e["date"] for e in events]
    assert dates == sorted(dates)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    reviews = [e for e in events if e["kind"] == "pr_review" and e["actor"] == TOMAS]
    assert len(reviews) == REVIEW_COUNT
