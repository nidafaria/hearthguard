"""Session guard for the real graphs: a changed org_xz or org_tallowdate fails the whole run.

The per-test fixture `real_graphs_untouched` reports a problem as a teardown error on one test.
This guard looks at the session as a whole: it fingerprints the real graphs before the first test
and after the last one, and if they differ it prints "real graph changed" in the summary and makes
pytest exit non-zero.

A graph that did not exist at the start is not a change: the `xz_org` fixture builds org_xz when
it is missing, and that load is reported as "created", not as a failure.
HEARTHGUARD_GUARDED_GRAPHS (comma separated) replaces the guarded names. Only the guard's own test
uses it, with a scratch graph.
"""

import os

REAL_GRAPHS = ("org_xz", "org_tallowdate")
WORDS = "real graph changed"


def guarded() -> tuple[str, ...]:
    raw = os.environ.get("HEARTHGUARD_GUARDED_GRAPHS", "")
    names = tuple(n.strip() for n in raw.split(",") if n.strip())
    return names or REAL_GRAPHS


def compare(before: dict, after: dict) -> tuple[list[str], list[str]]:
    """Returns (changed, created). A graph absent before and present after is created."""
    changed = [g for g in before if before[g] is not None and before[g] != after.get(g)]
    created = [g for g in before if before[g] is None and after.get(g) is not None]
    return changed, created


def snapshot() -> dict | None:
    """Fingerprints of the guarded graphs, or None when FalkorDB cannot be reached."""
    try:
        from core.graph.client import FalkorClient
        from tests.integration.scratch_graphs import fingerprint

        client = FalkorClient()
        return {g: fingerprint(client, g) for g in guarded()}
    except Exception:
        return None
