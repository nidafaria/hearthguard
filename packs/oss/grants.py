"""Documented source records -> Privilege, GRANTED, CAN_GRANT, APPROVED (docs/HEARTHGUARD.md §6.1).

Input is a list of plain records, each one a fact a documented public source states. Accepted
sources are listed in SOURCES. Anything else is refused, so an undocumented claim cannot become a
grant. The mapping is pure (map_records); write_records() MERGEs the result into an org graph.

Record shapes (hashed ids only; `actor` and `by` are already hid values):
  {"source": "MAINTAINERS", "kind": "grant",     "actor": h, "privilege": "release", "at": t,
   "by": h?, "ref": "<url or file path at a commit>"}
  {"source": "CODEOWNERS",  "kind": "can_grant", "actor": h, "privilege": "release",
   "approvals_required": 2, "ref": ...}
  {"source": "pr_review",   "kind": "approval",  "actor": h, "action_ref": "<commit sha>", "at": t,
   "ref": ...}

Rules:
  - privilege must be one of the OSS pack's kinds (packs/oss/pack.py); no other privilege is made.
  - a record with no `ref` is refused: nothing enters the graph without a place to check it.
  - a grant with no `at` is refused: the Rush detector needs the time.
  - nothing is inferred. A missing record means no edge, which the takeover checks report as
    NOT COMPUTED. xz has no such records, so its grant edges stay empty.
"""

from dataclasses import dataclass

from core.graph.client import FalkorClient
from packs.oss import pack

SOURCES = frozenset({"MAINTAINERS", "CODEOWNERS", "collaborator_permission", "pr_review"})
KINDS = frozenset({"grant", "can_grant", "approval"})
WRITE_TIMEOUT_MS = 30_000


class RefusedRecord(ValueError):
    """A source record the mapping will not turn into an edge."""


@dataclass
class Mapped:
    privileges: set
    granted: list
    can_grant: list
    approved: list


def _check(rec: dict) -> None:
    if rec.get("source") not in SOURCES:
        raise RefusedRecord(f"undocumented source: {rec.get('source')!r}")
    if rec.get("kind") not in KINDS:
        raise RefusedRecord(f"unknown record kind: {rec.get('kind')!r}")
    if not rec.get("ref"):
        raise RefusedRecord("a record needs a ref (where to check it)")
    if not rec.get("actor"):
        raise RefusedRecord("a record needs a hashed actor")
    if rec["kind"] in ("grant", "can_grant"):
        if rec.get("privilege") not in pack.PRIVILEGE_KINDS:
            raise RefusedRecord(f"not an OSS privilege: {rec.get('privilege')!r}")
    if rec["kind"] == "grant" and rec.get("at") is None:
        raise RefusedRecord("a grant needs a time")
    if rec["kind"] == "approval" and (not rec.get("action_ref") or rec.get("at") is None):
        raise RefusedRecord("an approval needs an action_ref and a time")


def map_records(records: list[dict]) -> Mapped:
    """Pure. Refuses any record that breaks a rule above; never guesses a missing field."""
    out = Mapped(privileges=set(), granted=[], can_grant=[], approved=[])
    for rec in records:
        _check(rec)
        if rec["kind"] == "grant":
            out.privileges.add(rec["privilege"])
            out.granted.append(
                {
                    "hid": rec["actor"],
                    "kind": rec["privilege"],
                    "at": rec["at"],
                    "by": rec.get("by"),
                    "ref": rec["ref"],
                }
            )
        elif rec["kind"] == "can_grant":
            out.privileges.add(rec["privilege"])
            out.can_grant.append(
                {
                    "hid": rec["actor"],
                    "kind": rec["privilege"],
                    "approvals_required": int(rec.get("approvals_required", 1)),
                    "ref": rec["ref"],
                }
            )
        else:
            out.approved.append({"hid": rec["actor"], "ref": rec["action_ref"], "at": rec["at"]})
    return out


def write_records(client: FalkorClient, graph: str, records: list[dict]) -> Mapped:
    """MERGE the mapped records into `graph`. Empty input writes nothing at all."""
    m = map_records(records)
    for kind in sorted(m.privileges):
        client.query(
            graph,
            "MERGE (:Privilege {kind: $k, sensitive: $s})",
            {"k": kind, "s": kind in pack.SENSITIVE_PRIVILEGES},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    if m.granted:
        client.query(
            graph,
            "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) MERGE (p:Privilege {kind: r.kind}) "
            "MERGE (a)-[g:GRANTED {at: r.at, evidence_ref: r.ref}]->(p) SET g.by_hid = r.by",
            {"rows": m.granted},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    if m.can_grant:
        client.query(
            graph,
            "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) MERGE (p:Privilege {kind: r.kind}) "
            "MERGE (a)-[c:CAN_GRANT]->(p) SET c.approvals_required = r.approvals_required, "
            "c.evidence_ref = r.ref",
            {"rows": m.can_grant},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    if m.approved:
        client.query(
            graph,
            "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) MERGE (x:Action {ref: r.ref}) "
            "MERGE (a)-[v:APPROVED {at: r.at}]->(x)",
            {"rows": m.approved},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    return m
