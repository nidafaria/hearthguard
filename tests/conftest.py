"""Suite-wide hooks. The real-graph guard is described in tests/real_graph_guard.py."""

import pytest

from tests import real_graph_guard as guard

_STATE: dict = {"before": None, "changed": [], "created": []}


def pytest_sessionstart(session):
    _STATE["before"] = guard.snapshot()


def pytest_sessionfinish(session, exitstatus):
    before = _STATE["before"]
    if before is None:
        return
    after = guard.snapshot()
    if after is None:
        return
    changed, created = guard.compare(before, after)
    _STATE["changed"], _STATE["created"] = changed, created
    if changed:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    if _STATE["changed"]:
        terminalreporter.write_sep("=", f"{guard.WORDS}: {', '.join(_STATE['changed'])}", red=True)
    if _STATE["created"]:
        terminalreporter.write_line(
            f"real graph created by the run: {', '.join(_STATE['created'])}"
        )
