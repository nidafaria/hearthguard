"""The playbook graph (docs/HEARTHGUARD.md 6.5): the detector spec hash, learned exceptions with
their state and gate results. Shared across orgs and packs.

No organisation data goes in here. An Exception node holds its template fields, its state, its
agreement count and its gate numbers. It does not hold an org id, a note id or an actor id. The
org side links to it by exception id (OwnerDecision.exception_id in the org graph).

Compiled investigation plans are not stored yet (blockers_E.md, row 43).
"""

import hashlib
import json
from pathlib import Path

from core.graph.client import FalkorClient
from core.learning import states

GRAPH = "playbook"
WRITE_MS = 10_000
READ_MS = 5_000
ROOT = Path(__file__).resolve().parents[2]
SPEC_FILES = ("core/detectors/*.py", "core/policy/decision.py")


def spec_hash(root: Path = ROOT) -> str:
    """A hash of the frozen detector code and the decision policy as they are on disk."""
    h = hashlib.sha256()
    for pattern in SPEC_FILES:
        for path in sorted(root.glob(pattern)):
            h.update(path.relative_to(root).as_posix().encode("utf-8"))
            h.update(path.read_bytes())
    return h.hexdigest()


def _ensure_spec(client: FalkorClient, graph: str, now: int) -> str:
    h = spec_hash()
    client.query(
        graph,
        "MERGE (s:DetectorSpec {hash: $h}) ON CREATE SET s.first_seen = $now",
        {"h": h, "now": now},
        timeout_ms=WRITE_MS,
    )
    return h


def record(client: FalkorClient, exc: dict, now: int, graph: str = GRAPH) -> dict:
    """Store one proposal. Idempotent per exception id: a second call changes nothing but the
    gate numbers and state it carries, and never resets agreements. Returns the stored node."""
    if exc["template"] is None:
        raise ValueError("only a proposal with a template is stored")
    h = _ensure_spec(client, graph, now)
    t = exc["template"]
    client.query(
        graph,
        """MATCH (s:DetectorSpec {hash: $h})
           MERGE (x:Exception {id: $id})
             ON CREATE SET x.exception = $name, x.applies_to = $applies, x.when = $when,
                           x.effect = $effect, x.agreements = 1, x.created_at = $now
           MERGE (x)-[:UNDER]->(s)
           SET x.gate = $gate, x.updated_at = $now""",
        {
            "h": h,
            "id": exc["exception_id"],
            "name": t["exception"],
            "applies": t["applies_to"],
            "when": t["when"],
            "effect": t["effect"],
            "gate": json.dumps(exc["gate"], sort_keys=True) if exc["gate"] else None,
            "now": now,
        },
        timeout_ms=WRITE_MS,
    )
    return set_state(client, exc["exception_id"], exc["state"], exc["state_reason"], now, graph)


def count_agreement(client: FalkorClient, xid: str, now: int, graph: str = GRAPH) -> int:
    """One more independent dismissal proposed this template. Called once per new dismissal."""
    r = client.query(
        graph,
        "MATCH (x:Exception {id: $id}) SET x.agreements = coalesce(x.agreements, 0) + 1, "
        "x.updated_at = $now RETURN x.agreements",
        {"id": xid, "now": now},
        timeout_ms=WRITE_MS,
    )
    return int(r.result_set[0][0]) if r.result_set else 0


def set_state(
    client: FalkorClient, xid: str, state: str, reason: str, now: int, graph: str = GRAPH
) -> dict:
    if state not in states.STATES:
        raise ValueError(f"unknown state {state!r}")
    client.query(
        graph,
        "MATCH (x:Exception {id: $id}) SET x.state = $state, x.state_reason = $reason, "
        "x.updated_at = $now",
        {"id": xid, "state": state, "reason": reason, "now": now},
        timeout_ms=WRITE_MS,
    )
    return get(client, xid, graph)


def approve(client: FalkorClient, xid: str, now: int, graph: str = GRAPH) -> dict | None:
    """The owner approves a Shadow exception. Only a Shadow one can be approved."""
    r = client.query(
        graph,
        "MATCH (x:Exception {id: $id}) WHERE x.state = $shadow "
        "SET x.state = $adopted, x.state_reason = 'owner approved after passing the gate', "
        "x.owner_approved_at = $now, x.updated_at = $now RETURN x.id",
        {"id": xid, "shadow": states.SHADOW, "adopted": states.ADOPTED, "now": now},
        timeout_ms=WRITE_MS,
    )
    return get(client, xid, graph) if r.result_set else None


def get(client: FalkorClient, xid: str, graph: str = GRAPH) -> dict | None:
    r = client.query(
        graph,
        "MATCH (x:Exception {id: $id}) RETURN properties(x)",
        {"id": xid},
        timeout_ms=READ_MS,
    )
    return _clean(dict(r.result_set[0][0])) if r.result_set else None


def list_exceptions(client: FalkorClient, graph: str = GRAPH) -> dict:
    r = client.query(
        graph,
        "MATCH (x:Exception) RETURN properties(x) ORDER BY x.created_at, x.id LIMIT 200",
        timeout_ms=READ_MS,
    )
    spec = client.query(
        graph,
        "MATCH (s:DetectorSpec) RETURN s.hash ORDER BY s.first_seen LIMIT 20",
        timeout_ms=READ_MS,
    )
    return {
        "graph": graph,
        "spec_hashes": [row[0] for row in spec.result_set],
        "exceptions": [_clean(dict(row[0])) for row in r.result_set],
        "states": list(states.STATES),
    }


def _clean(x: dict) -> dict:
    if x.get("gate"):
        x["gate"] = json.loads(x["gate"])
    return x
