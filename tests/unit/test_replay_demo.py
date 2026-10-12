"""The replay and the demo: every cell comes from a saved file, and two runs print the same bytes.

The hand-built inputs below stand in for the four result files. Expected cells are written in the
comments before the assertions.
"""

import json

import pytest

from eval import demo, replay_xz


def write_inputs(root, unread=7):
    (root / "xz_normal.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "quarter": "2022-Q1",
                        "metrics": [
                            {
                                "metric": "cadence_days",
                                "status": "COMPUTED",
                                "value": 0.5,
                                "unit": "days",
                                "n": 10,
                            },
                            {
                                "metric": "active_keepers",
                                "status": "COMPUTED",
                                "value": 3,
                                "unit": "actors",
                                "n": 3,
                            },
                            {
                                "metric": "grant_days",
                                "status": "NOT COMPUTED",
                                "value": None,
                                "unit": None,
                                "n": None,
                            },
                        ],
                    }
                ]
            }
        )
    )
    checks = {
        n: {"status": "NOT_COMPUTED", "reason": f"{n} reason"}
        for n in ("rush", "bypass", "lone_keeper")
    }
    checks["takeover_cost"] = {"status": "NOT COMPUTED", "reason": "tc"}
    checks["guardians"] = {"status": "NOT COMPUTED", "reason": "g"}
    (root / "xz_quarterly_status.json").write_text(
        json.dumps({"quarters": [{"quarter": "2022-Q1", "checks": checks}]})
    )
    (root / "pressure_vouch_status.json").write_text(
        json.dumps(
            {
                "coverage": {
                    "read_so_far": 5,
                    "to_read": 9,
                    "complete": False,
                    "excluded_human_labelled_test_set": 2,
                },
                "quarters": [
                    {
                        "quarter": "2022-Q1",
                        "pressure": {"status": "NOT_FIRED", "reason": "p"},
                        "vouch": {"status": "NOT_COMPUTED", "reason": "v"},
                        "window_coverage": {"pressure": {"unread": unread}},
                    }
                ],
            }
        )
    )
    (root / "decision_status.json").write_text(
        json.dumps(
            {
                "quarters": [
                    {
                        "quarter": "2022-Q1",
                        "T_iso": "2022-03-31T23:59:59Z",
                        "decision": "HOLD",
                        "detail": {"reason": "move unknown: RUSH"},
                    }
                ]
            }
        )
    )


def test_every_cell_is_copied_from_a_named_file(tmp_path):
    write_inputs(tmp_path)
    doc = replay_xz.build(tmp_path)
    row = doc["quarters"][0]
    # cadence 0.5 days, 3 keepers (computed); grant_days is not one of the replayed metrics.
    assert row["normal"]["cadence_days"]["value"] == 0.5
    assert row["normal"]["active_keepers"]["value"] == 3
    assert "grant_days" not in row["normal"]
    # "NOT COMPUTED" (takeover) and "NOT_COMPUTED" (rush) are shown the same way.
    assert row["checks"]["takeover_cost"]["status"] == "NOT COMPUTED"
    assert row["checks"]["rush"]["status"] == "NOT COMPUTED"
    assert row["checks"]["pressure"]["status"] == "NOT_FIRED"
    assert row["checks"]["vouch"]["status"] == "NOT COMPUTED"
    assert row["reader_unread_in_pressure_window"] == 7
    assert row["decision"] == {
        "type": "HOLD",
        "reason": "move unknown: RUSH",
        "source": "decision_status.json",
    }
    for cell in (*row["checks"].values(), *row["normal"].values(), row["decision"]):
        assert cell["source"].endswith(".json")


def test_the_table_row_matches_the_inputs(tmp_path):
    write_inputs(tmp_path)
    text = replay_xz.markdown(replay_xz.build(tmp_path))
    expected = (
        "| 2022-Q1 | 0.5000 | 3 | NOT COMPUTED | NOT COMPUTED | NOT COMPUTED | NOT COMPUTED | "
        "NOT COMPUTED | NOT_FIRED | NOT COMPUTED | 7 | HOLD |"
    )
    assert expected in text
    assert "5 of 9 messages read (INCOMPLETE)" in text


def test_missing_files_are_named_and_nothing_is_invented(tmp_path):
    write_inputs(tmp_path)
    (tmp_path / "decision_status.json").unlink()
    assert replay_xz.missing(tmp_path) == ["decision_status.json"]


def test_replay_output_has_no_timestamp_so_two_builds_are_identical(tmp_path):
    write_inputs(tmp_path)
    a = replay_xz.markdown(replay_xz.build(tmp_path))
    b = replay_xz.markdown(replay_xz.build(tmp_path))
    assert a == b and json.dumps(replay_xz.build(tmp_path)) == json.dumps(replay_xz.build(tmp_path))


def test_demo_prints_identical_output_twice_with_no_network_or_key(capsys, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    import socket

    def no_network(*a, **k):
        raise AssertionError("the demo opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    if replay_xz.missing(replay_xz.RESULTS):
        pytest.skip("result files not built yet")
    assert demo.main() == 0
    first = capsys.readouterr().out
    assert demo.main() == 0
    second = capsys.readouterr().out
    assert first == second and "| quarter |" in first


def test_demo_says_what_is_missing_instead_of_inventing(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(replay_xz, "RESULTS", tmp_path)
    assert demo.main() == 1
    assert "missing result files" in capsys.readouterr().out
