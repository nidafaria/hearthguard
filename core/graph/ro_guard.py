"""Read-only guard for exploratory and detector queries (CLAUDE.md, docs/HEARTHGUARD.md §8.1).

Two layers:
1. check_read_only() rejects a query client-side, before any network call. It blocks write
   keywords, write-type index procedures, and queries with no literal LIMIT at or under the cap.
2. ro_query() sends the query with GRAPH.RO_QUERY, which FalkorDB also refuses for writes.

Keywords inside comments, string literals and backtick names are not matched. The Cypher parser
also treats those as text or names, so they cannot write.
"""

import re

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient, require_timeout

# Policy cap, not a measured value. Exploratory queries must ask for at most this many rows.
MAX_LIMIT = 1000

WRITE_KEYWORDS: tuple[str, ...] = (
    "CREATE",
    "MERGE",
    "SET",
    "DELETE",
    "DETACH",
    "REMOVE",
    "DROP",
    "FOREACH",
    "LOAD",
)

# Index create/drop procedures write schema. Reads such as queryNodes stay allowed.
_WRITE_PROCEDURE = re.compile(r"\bCALL\s+db\.idx\.[\w.]*?(create|drop)\w*", re.IGNORECASE)
_LIMIT = re.compile(r"\bLIMIT\s+(\S+)", re.IGNORECASE)


class ReadOnlyViolation(ValueError):
    """The query was rejected before it reached the server."""


def _strip_text(cypher: str) -> str:
    """Blank out comments, string literals and backtick names so only real syntax is checked."""
    s = re.sub(r"//[^\n]*", " ", cypher)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    s = re.sub(r"'(?:\\.|[^'\\])*'", "''", s)
    s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
    s = re.sub(r"`[^`]*`", "``", s)
    return s


def check_read_only(cypher: str) -> None:
    """Raise ReadOnlyViolation unless `cypher` is a read with a literal LIMIT under the cap."""
    code = _strip_text(cypher)
    for kw in WRITE_KEYWORDS:
        if re.search(rf"\b{kw}\b", code, re.IGNORECASE):
            raise ReadOnlyViolation(f"write keyword '{kw}' is not allowed in a read-only query")
    if _WRITE_PROCEDURE.search(code):
        raise ReadOnlyViolation("index create/drop procedures are not allowed in a read-only query")
    limits = _LIMIT.findall(code)
    if not limits:
        raise ReadOnlyViolation(f"read-only queries must have a LIMIT of at most {MAX_LIMIT}")
    for raw in limits:
        if not raw.isdigit() or int(raw) > MAX_LIMIT:
            raise ReadOnlyViolation(
                f"LIMIT must be a literal integer of at most {MAX_LIMIT}, got '{raw}'"
            )


def ro_query(
    client: FalkorClient,
    graph: str,
    cypher: str,
    params: dict | None = None,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
):
    """Run a checked read through GRAPH.RO_QUERY. A rejected query never reaches the server."""
    check_read_only(cypher)
    return client.graph(graph).ro_query(cypher, params=params, timeout=require_timeout(timeout_ms))
