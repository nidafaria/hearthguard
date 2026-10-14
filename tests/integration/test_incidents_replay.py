"""event-stream and axios replays (spec §10.2) on a real FalkorDB. No mocks.

Needs data/raw/incidents/ (`uv run python -m eval.incidents_fetch`); without it the tests skip.

Hand-worked expectations (from the cached files; times UTC):
  event-stream: e0 = 3.3.4 (2016-07-17). Points: 3.3.5 2018-09-05, 3.3.6 2018-09-09, 4.0.0
    2018-09-16, 4.0.1 2018-09-29 (the public report is 2018-11-20). At 3.3.5 Bypass has no
    earlier release inside 730 days (3.3.4 is 780 days back) -> NOT_COMPUTED. 3.3.6 has no Path ->
    NOT_COMPUTED. The decision is HOLD until Bypass fires at 4.0.0, so the first NOTE is AFTER the
    malicious release (3.3.6): the lead time to it is negative.
  axios: e0 = 1.14.0 (2026-03-27). Points: 1.14.1 2026-03-31T00:21:58Z and 0.30.4 01:00:57Z. Channel
    and CI MATCH the 730-day normal (33 of 37 releases were manual), so Bypass does not fire.
  Both: nothing is written to the org graph by a replay, and the output has no raw name.
"""

import json
from pathlib import Path

import pytest

from eval import incidents_replay as rp
from eval import replay_axios, replay_event_stream
from packs.oss import incidents_graph as ig

pytestmark = pytest.mark.skipif(
    not (ig.RAW / "event_stream" / "npm_event-stream.json").is_file(),
    reason="data/raw/incidents is absent (git-ignored): run eval.incidents_fetch",
)
RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"


@pytest.fixture(scope="module")
def graphs(client):
    from eval import incidents_load as il

    il.run(client)  # org_event_stream and org_axios, idempotent
    return client


def test_event_stream_first_note_comes_after_the_malicious_release(graphs):
    doc = replay_event_stream.run(graphs)["replay"]
    got = [(p["at_utc"], p["moves"]["BYPASS"], p["decision"]) for p in doc["points"]]
    assert got == [
        ("2018-09-05T05:27:47Z", "NOT_COMPUTED", "HOLD"),
        ("2018-09-09T08:28:59Z", "NOT_COMPUTED", "HOLD"),
        ("2018-09-16T11:20:20Z", "FIRED", "NOTE"),
        ("2018-09-29T06:55:49Z", "FIRED", "NOTE"),
    ]
    assert doc["first_fire_utc"] == "2018-09-16T11:20:20Z"
    assert doc["lead_time_days_to_malicious_release"] < 0  # after it, and said so
    assert doc["lead_time_days_to_public_report"] > 60
    assert doc["first_move_fired_to_malicious_release_days"] > 0  # Rush fired 4 days before


def test_axios_bypass_does_not_fire(graphs):
    doc = replay_axios.run(graphs)
    for name in ("with_secondary_record", "registry_only"):
        r = doc[name]
        assert [p["at_utc"] for p in r["points"]] == [
            "2026-03-31T00:21:58Z",
            "2026-03-31T01:00:57Z",
        ]
        assert r["fired"] is False and r["bypass_fired_at"] == []
        assert all(p["moves"]["BYPASS"] == "NOT_COMPUTED" for p in r["points"])
    ch = doc["release_channels_before_incident"]["counts_by_window"]
    assert ch["trailing_730d"] == {"npm_trusted_publisher": 4, "npm_user": 33}
    assert ch["trailing_90d"]["npm_trusted_publisher"] == 4


def test_a_replay_writes_nothing_and_leaves_no_copy(graphs):
    def snapshot():
        return {g: ig.counts(graphs, g) for g in ("org_event_stream", "org_axios")}

    before = snapshot()
    replay_event_stream.run(graphs)
    replay_axios.run(graphs)
    assert snapshot() == before
    names = {
        g if isinstance(g, str) else g.decode() for g in graphs.db.execute_command("GRAPH.LIST")
    }
    assert not {n for n in names if n.startswith(("org_axiosreg", "takeover_"))}


def test_saved_results_exist_and_carry_no_raw_name():
    for name in ("replay_event_stream.json", "replay_axios.json"):
        text = (RESULTS / name).read_text("utf-8")
        d = json.loads(text)
        assert d["definitions"] and d["honesty"] and d["case_notes"]
        for raw in ("jasonsaayman", "dominictarr", "proton.me"):
            assert raw not in text, (name, raw)
    assert rp.DEFINITIONS["negative_lead_time"]
