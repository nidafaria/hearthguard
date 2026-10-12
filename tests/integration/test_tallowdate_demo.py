"""Every demo beat reads from an existing file and field; a missing field reads NOT COMPUTED."""

import json

from redteam.tallowdate_demo_script import ROOT, _beats, _resolve

DEMO = ROOT / "eval" / "results" / "tallowdate_demo_script.json"


def test_every_beat_points_to_an_existing_file():
    for beat in _beats():
        for key, (path, _field) in beat["reads"].items():
            assert (ROOT / path).exists(), f"{beat['beat']}.{key}: {path} does not exist"


def test_every_read_matches_its_field_or_is_not_computed():
    saved = json.loads(DEMO.read_text(encoding="utf-8"))["beats"]
    by_name = {b["beat"]: b for b in saved}
    for beat in _beats():
        out = by_name[beat["beat"]]
        for key, (path, field) in beat["reads"].items():
            found, value = _resolve(path, field)
            recorded = out["reads"][key]
            assert recorded["found"] is found, f"{beat['beat']}.{key}"
            if found:
                assert recorded["value"] == value, f"{beat['beat']}.{key}"
            else:
                assert recorded["value"] == "NOT COMPUTED", f"{beat['beat']}.{key}"
