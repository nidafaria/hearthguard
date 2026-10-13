"""The `why` query of spec 7.6: a Finding, the evidence behind it, each quote and its source link.

The query runs live through the read-only guard (GRAPH.RO_QUERY, write-keyword block, literal
LIMIT) with an explicit timeout. Its Cypher and wall-clock time are returned with the rows.
Each fact's status and reason come from the saved status files the decision was built from; the
quotes and links come from the graph. No model is called.
"""

import json
import re
import time
from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents.cases import MOVES, Case, read_json
from core.graph.client import FalkorClient
from core.graph.ro_guard import ro_query

WHY_TIMEOUT_MS = 10_000

# Spec 7.6, with properties(e) in place of the node itself and a literal LIMIT for the guard.
WHY_CYPHER = (
    "MATCH (f:Finding {id: $id})-[:SUPPORTED_BY]->(e)\n"
    "OPTIONAL MATCH (e)-[:FROM]->(s:Span)<-[:HAS]-(src:Source)\n"
    "RETURN f.moves AS moves, labels(e)[0] AS kind, properties(e) AS props,\n"
    "       s.text AS quote, src.url AS link, src.ref AS ref, src.type AS source_type\n"
    "ORDER BY kind, ref LIMIT 200"
)

FACT_CLAIMS = {
    "PRESSURE": ("PRESSURE", "URGENCY"),
    "VOUCH": ("VOUCH",),
}
FACT_ORDER = (*MOVES, "LONE_KEEPER")
_MSG = re.compile(r"^msg(\d+)$")

# Copied from packs/oss/mail_cache.py (BASE and msg_name). They must match it. core never imports
# packs; tests/unit/test_why_archive_link.py checks that both build the same link.
ARCHIVE_BASE = "https://www.mail-archive.com/xz-devel@tukaani.org/"
ARCHIVE_NAME = "msg{n:05d}.html"


def source_link(source_type: str | None, ref: str | None, url: str | None) -> str | None:
    """The stored URL, or for a cached mailing-list message the archive URL of that message."""
    if url:
        return url
    if source_type == "mail" and ref:
        m = _MSG.match(ref)
        if m:
            return ARCHIVE_BASE + ARCHIVE_NAME.format(n=int(m.group(1)))
    return None


def _node_for(q: dict, key: str) -> dict | None:
    if key in q and isinstance(q[key], dict):
        return q[key]
    return q.get("checks", {}).get(key)


def saved_facts(case: Case, row: dict, results: Path) -> list[dict]:
    """Each fact with its status, reason, source file and the queries saved with it.

    Raises ValueError if a status file disagrees with the decision row.
    """
    out = []
    for fact in FACT_ORDER:
        key = fact.lower()
        recorded = row["lone_keeper"] if fact == "LONE_KEEPER" else row["moves"][fact]
        node, file_name = None, None
        for name in case.detail_files:
            path = results / name
            if not path.exists():
                continue
            for q in read_json(path)["quarters"]:
                if q["quarter"] == row["quarter"] and _node_for(q, key) is not None:
                    node, file_name = _node_for(q, key), name
                    break
            if node is not None:
                break
        if node is None:
            out.append(
                {
                    "fact": fact,
                    "status": recorded,
                    "reason": row["reasons"].get(fact, "no saved reason"),
                    "file": None,
                    "saved_queries": [],
                }
            )
            continue
        status = node["status"].replace("NOT COMPUTED", "NOT_COMPUTED")
        if status != recorded:
            raise ValueError(
                f"{row['quarter']} {fact}: decision says {recorded}, file says {status}"
            )
        out.append(
            {
                "fact": fact,
                "status": status,
                "reason": node.get("reason") or row["reasons"].get(fact, "no saved reason"),
                "file": file_name,
                "saved_queries": [
                    {
                        "name": q["name"],
                        "query": q["query"],
                        "rows": q["rows"],
                        "ms": q.get("ms") or 0,
                    }
                    for q in node.get("queries", [])
                ],
            }
        )
    return out


def run_why(client: FalkorClient, case: Case, quarter: str) -> dict:
    """Run the 7.6 why query live. Returns rows and the query record (Cypher, ms, timeout)."""
    params = {"id": ig.finding_id(case, quarter)}
    start = time.perf_counter()
    res = ro_query(client, case.graph, WHY_CYPHER, params, timeout_ms=WHY_TIMEOUT_MS)
    ms = (time.perf_counter() - start) * 1000
    rows = []
    for _moves, kind, props, quote, link, ref, stype in res.result_set:
        rows.append(
            {
                "kind": kind,
                "props": dict(props),
                "quote": quote,
                "link": source_link(stype, ref, link),
                "source_ref": ref,
            }
        )
    return {
        "rows": rows,
        "query": {
            "cypher": WHY_CYPHER,
            "params": params,
            "ms": round(ms, 2),
            "rows": len(rows),
            "timeout_ms": WHY_TIMEOUT_MS,
            "guard": "GRAPH.RO_QUERY with write-keyword block and LIMIT 200",
        },
    }


def build_why(client: FalkorClient, case: Case, row: dict, results: Path) -> dict:
    live = run_why(client, case, row["quarter"])
    facts = saved_facts(case, row, results)
    claim_rows = [r for r in live["rows"] if r["kind"] == "Claim"]
    for f in facts:
        kinds = FACT_CLAIMS.get(f["fact"], ())
        f["evidence"] = [r for r in claim_rows if r["props"].get("kind") in kinds]
    other = [
        r
        for r in live["rows"]
        if r["kind"] != "Claim"
        or r["props"].get("kind") not in {k for ks in FACT_CLAIMS.values() for k in ks}
    ]
    return {
        "facts": facts,
        "other_evidence": other,
        "live_query": live["query"],
        "saved_query_ms": round(sum(q["ms"] for f in facts for q in f["saved_queries"]), 2),
        "rule": row["detail"].get("breakdown", {}).get("rule", "not recorded"),
    }


def dumps(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2)
