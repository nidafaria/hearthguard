"""As-of-T helper: every detector reads only events with at <= $T (docs/HEARTHGUARD.md §9).

Use as_of_fragment() in a WHERE clause and pass T in the parameters. Use run_as_of() to run a
query. It refuses a missing T and a query that never references $T, before any server call.
Checking for "$T" in the text is a minimum check. It does not prove the filter is correct.
"""

import re
from collections.abc import Mapping
from typing import Any

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import ro_query

AS_OF_PARAM = "T"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MissingAsOfError(ValueError):
    """A detector query was about to run without an as-of time T."""


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"not a plain identifier: {name!r}")
    return name


def as_of_fragment(alias: str, prop: str = "at") -> str:
    """Parameterised condition `alias.prop <= $T`. Use it inside a WHERE clause."""
    return f"{_ident(alias)}.{_ident(prop)} <= ${AS_OF_PARAM}"


def with_as_of(params: Mapping[str, Any] | None, T: Any) -> dict[str, Any]:
    """Return a copy of params with T set. Refuses T=None."""
    if T is None:
        raise MissingAsOfError("as-of T is required; got None")
    return {**(params or {}), AS_OF_PARAM: T}


def run_as_of(
    client: FalkorClient,
    graph: str,
    cypher: str,
    params: Mapping[str, Any] | None = None,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
):
    """Run a checked read that filters on $T. Refuses a missing T or a query without $T."""
    p = dict(params or {})
    if p.get(AS_OF_PARAM) is None:
        raise MissingAsOfError("as-of query needs parameter T (not None)")
    if f"${AS_OF_PARAM}" not in cypher:
        raise MissingAsOfError("as-of query must reference $T in its Cypher")
    return ro_query(client, graph, cypher, p, timeout_ms=timeout_ms)
