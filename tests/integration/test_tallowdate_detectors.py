"""Detector status for tallowdate: same function code as the xz run, and every check is labelled."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DETECTORS = ROOT / "eval" / "results" / "tallowdate_detector_status.json"


def test_detector_functions_match_the_xz_run():
    doc = json.loads(DETECTORS.read_text(encoding="utf-8"))
    hashes = doc["function_hashes"]
    assert set(hashes) == {"rush", "bypass", "lone_keeper", "takeover_cost", "guardians"}
    mismatched = [k for k, v in hashes.items() if not v["match"]]
    assert mismatched == [], f"detector source differs from the xz run: {mismatched}"


def test_detector_status_is_labelled_and_pressure_vouch_not_run():
    doc = json.loads(DETECTORS.read_text(encoding="utf-8"))
    assert doc["synthetic"] is True and doc["case"] == "tallowdate"
    for q in doc["quarters"]:
        assert q["checks"]["pressure"]["status"] == "NOT COMPUTED"
        assert q["checks"]["pressure"]["reason"] == (
            "reader not run on synthetic case in this step"
        )
        assert q["checks"]["vouch"]["status"] == "NOT COMPUTED"
