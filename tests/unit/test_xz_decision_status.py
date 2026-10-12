"""The decision status script feeds saved detector statuses to the policy and adds no branch.

Expected decisions are worked out by hand from the frozen decide() (spec 7.3):
- every move NOT_COMPUTED/NOT_FIRED with at least one unknown -> HOLD("move unknown: ...")
  (decide_with_unknowns, PROPOSED, decision 0002);
- every move NOT_FIRED -> NO_ACTION;
- Pressure and Vouch FIRED, lone keeper unknown (passed as False, risk 1.0): 2 moves, 2.0 < 3.0
  -> NOTE(takeover-moves, medium);
- Bypass FIRED -> NOTE(path-bypass, high).
"""

import json

from eval import xz_decision_status as xds


def run(tmp_path, monkeypatch, pressure, vouch, rush="NOT_COMPUTED", bypass="NOT_COMPUTED"):
    pv = {
        "quarters": [
            {
                "quarter": "2022-Q1",
                "T_iso": "2022-03-31T23:59:59Z",
                "pressure": {"status": pressure, "reason": "p"},
                "vouch": {"status": vouch, "reason": "v"},
            }
        ]
    }
    checks = {
        "rush": {"status": rush, "reason": "r"},
        "bypass": {"status": bypass, "reason": "b"},
        "lone_keeper": {"status": "NOT_COMPUTED", "reason": "l"},
    }
    qs = {"quarters": [{"quarter": "2022-Q1", "checks": checks}]}
    (tmp_path / "pv.json").write_text(json.dumps(pv))
    (tmp_path / "qs.json").write_text(json.dumps(qs))
    monkeypatch.setattr(xds, "PV", tmp_path / "pv.json")
    monkeypatch.setattr(xds, "QS", tmp_path / "qs.json")
    return xds.build()["quarters"][0]


def test_unknown_moves_give_hold_not_no_action(tmp_path, monkeypatch):
    row = run(tmp_path, monkeypatch, "NOT_FIRED", "NOT_FIRED")
    assert row["decision"] == "HOLD" and "RUSH" in row["detail"]["reason"]
    assert row["moves"] == {
        "PRESSURE": "NOT_FIRED",
        "VOUCH": "NOT_FIRED",
        "RUSH": "NOT_COMPUTED",
        "BYPASS": "NOT_COMPUTED",
    }


def test_all_moves_not_fired_is_no_action(tmp_path, monkeypatch):
    row = run(tmp_path, monkeypatch, "NOT_FIRED", "NOT_FIRED", "NOT_FIRED", "NOT_FIRED")
    assert row["decision"] == "NO_ACTION"


def test_two_fired_moves_give_a_medium_note(tmp_path, monkeypatch):
    row = run(tmp_path, monkeypatch, "FIRED", "FIRED", "NOT_FIRED", "NOT_FIRED")
    assert row["decision"] == "NOTE"
    assert (row["detail"]["pattern"], row["detail"]["urgency"]) == ("takeover-moves", "medium")


def test_bypass_alone_gives_a_high_note(tmp_path, monkeypatch):
    row = run(tmp_path, monkeypatch, "NOT_FIRED", "NOT_FIRED", "NOT_FIRED", "FIRED")
    assert row["decision"] == "NOTE" and row["detail"]["urgency"] == "high"


def test_takeover_style_not_computed_spelling_is_normalised():
    assert xds.norm("NOT COMPUTED") == "NOT_COMPUTED" and xds.norm("FIRED") == "FIRED"


def test_it_refuses_when_an_input_file_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(xds, "PV", tmp_path / "none.json")
    monkeypatch.setattr(xds, "QS", tmp_path / "none2.json")
    assert xds.main() == 1
    assert "does not exist yet" in capsys.readouterr().out
