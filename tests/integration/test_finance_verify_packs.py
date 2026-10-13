"""verify-packs (spec §4.2): the finance company runs with the OSS pack removed, same result."""

import json

from eval import verify_packs


def test_finance_runs_with_the_oss_pack_removed_and_gives_the_same_result():
    assert verify_packs.main() == 0
    out = json.loads(verify_packs.RESULT.read_text(encoding="utf-8"))
    assert out["passed"] is True
    assert out["checks"]["removal"]["oss_pack_present_in_tree"] is False
    assert out["checks"]["same_result"]["ok"] is True
