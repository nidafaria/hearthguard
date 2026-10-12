"""The session guard fails the run, with the words "real graph changed", when a guarded graph moves.

Expected values worked out first:
  - a scratch graph starts with 1 node; an inner test adds a second;
  - the inner run therefore exits non-zero and its summary holds "real graph changed";
  - a second inner run whose test changes nothing exits 0 and the words are absent.
The inner runs guard a scratch graph through HEARTHGUARD_GUARDED_GRAPHS. The real graphs are
never written by this test.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from core.graph.client import FalkorClient
from tests import real_graph_guard as guard
from tests.integration.scratch_graphs import drop_owned, new_org_id

ROOT = Path(__file__).resolve().parents[2]


def test_compare_is_pure():
    before = {"a": ("x",), "b": None, "c": ("y",)}
    after = {"a": ("x", "z"), "b": ("q",), "c": ("y",)}
    assert guard.compare(before, after) == (["a"], ["b"])


def _inner(tmp: Path, graph: str, body: str) -> subprocess.CompletedProcess:
    (tmp / "conftest.py").write_text(
        "from tests.conftest import (pytest_sessionfinish, pytest_sessionstart,\n"
        "    pytest_terminal_summary)\n",
        encoding="utf-8",
    )
    (tmp / "test_inner.py").write_text(
        textwrap.dedent(
            f"""
            from core.graph.client import FalkorClient

            def test_inner():
                {body}
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "HEARTHGUARD_GUARDED_GRAPHS": graph}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp),
            "-p",
            "no:cacheprovider",
            "-q",
            "--rootdir",
            str(tmp),
            "-c",
            os.devnull,
        ],
        cwd=ROOT,
        env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_changed_guarded_graph_fails_the_run(tmp_path):
    org = new_org_id()
    graph = f"org_{org}"
    client = FalkorClient()
    try:
        client.query(graph, "CREATE (:Org {id: 'x'})", timeout_ms=10_000)
        res = _inner(
            tmp_path,
            graph,
            f"FalkorClient().query('{graph}', 'CREATE (:Org {{id: \"y\"}})', timeout_ms=10_000)",
        )
        assert res.returncode != 0, res.stdout
        assert guard.WORDS in res.stdout, res.stdout
        assert graph in res.stdout
    finally:
        drop_owned(client, org)


def test_unchanged_guarded_graph_passes(tmp_path):
    org = new_org_id()
    graph = f"org_{org}"
    client = FalkorClient()
    try:
        client.query(graph, "CREATE (:Org {id: 'x'})", timeout_ms=10_000)
        res = _inner(tmp_path, graph, "pass")
        assert res.returncode == 0, res.stdout
        assert guard.WORDS not in res.stdout
    finally:
        drop_owned(client, org)
