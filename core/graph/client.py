"""Thin wrapper over the falkordb client: explicit per-query timeouts and GRAPH.COPY.

Every query takes a timeout in milliseconds. The server enforces it and fails with
"Query timed out" (docs/VERIFIED.md). There is no unbounded default.
"""

import os
from typing import Any

from dotenv import load_dotenv
from falkordb import FalkorDB, Graph
from falkordb.query_result import QueryResult
from redis.exceptions import ResponseError

DEFAULT_TIMEOUT_MS = 5000


def require_timeout(timeout_ms: int) -> int:
    """Every query needs an explicit positive timeout in milliseconds."""
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms <= 0:
        raise ValueError("timeout_ms must be a positive integer number of milliseconds")
    return timeout_ms


class FalkorClient:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        load_dotenv()
        self.host = host or os.environ.get("FALKORDB_HOST", "localhost")
        self.port = port or int(os.environ.get("FALKORDB_PORT", "6379"))
        self._db: FalkorDB | None = None

    @property
    def db(self) -> FalkorDB:
        """Connect on first use, so building a client never touches the network."""
        if self._db is None:
            self._db = FalkorDB(host=self.host, port=self.port)
        return self._db

    def graph(self, name: str) -> Graph:
        return self.db.select_graph(name)

    def query(
        self,
        name: str,
        cypher: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> QueryResult:
        return self.graph(name).query(cypher, params=params, timeout=require_timeout(timeout_ms))

    def copy(self, src: str, dst: str) -> None:
        """GRAPH.COPY: dst becomes an independent copy of src. Fails if dst already exists."""
        self.db.execute_command("GRAPH.COPY", src, dst)

    def drop(self, name: str) -> None:
        """Delete a graph. A graph that does not exist is not an error."""
        try:
            self.db.execute_command("GRAPH.DELETE", name)
        except ResponseError as e:
            if "empty key" not in str(e):
                raise
