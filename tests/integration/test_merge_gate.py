"""Row 26: a client asks check_trust over MCP stdio before a merge, on a real FalkorDB.

The org is the b_two_keepers fixture (keepers A and B hold release) plus one newcomer N with one
action. Expected: the child server lists the nine tools; check_trust returns evidence, not a
verdict; N is low-history; N holds nothing; the raw identifier is not echoed; the org graph is the
same after the call as before.
"""

import json
import uuid
from pathlib import Path

import pytest

from core.graph.hashing import identifier_hash
from eval import merge_gate
from tests.fixtures.takeover_cases import CASES

FIXTURE = next(c for c in CASES if c.name == "b_two_keepers")
NEWCOMER = "newcomer@example.invalid"
SAVED = Path(merge_gate.RESULT)


@pytest.fixture
def org(client):
    org = "mg" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    client.drop(g)
    FIXTURE.build(client, g)
    hid = identifier_hash(NEWCOMER)
    client.query(g, "MERGE (:Actor {hid: $h, kind: 'human', first_seen_in_org: 990000})", {"h": hid})
    client.query(
        g,
        "MATCH (a:Actor {hid: $h}) "
        "CREATE (a)-[:DID {at: 991000}]->(:Action {ref: 'x1', kind: 'commit', at: 991000})",
        {"h": hid},
    )
    yield {"org": org, "graph": g, "hid": hid}
    client.drop(g)


def _fingerprint(client, g):
    return (
        client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set,
        client.query(g, "MATCH ()-[e]->() RETURN count(e)", timeout_ms=30_000).result_set,
    )


def test_a_client_gets_evidence_over_stdio_and_nothing_is_written(client, org):
    before = _fingerprint(client, org["graph"])
    out = merge_gate.run(org["org"], NEWCOMER, "release")
    assert len(out["tools_listed"]) == 9 and "check_trust" in out["tools_listed"]
    ev = out["evidence"]
    assert ev["actor_hid"] == org["hid"]
    assert ev["history"]["status"] == "COMPUTED" and ev["history"]["low_history"] is True
    assert ev["already_holds"] == []
    assert "score" not in ev and "verdict" not in ev
    assert NEWCOMER not in json.dumps(out)
    assert out["synthetic"] is False
    assert _fingerprint(client, org["graph"]) == before


def test_the_saved_demo_is_the_synthetic_case_and_gives_no_verdict():
    saved = json.loads(SAVED.read_text(encoding="utf-8"))
    assert saved["org"] == "tallowdate" and saved["synthetic"] is True
    assert "check_trust" in saved["tools_listed"]
    assert saved["evidence"]["trust_path"]["status"] == "NOT COMPUTED"
    assert "score" not in saved["evidence"] and "verdict" not in saved["evidence"]
