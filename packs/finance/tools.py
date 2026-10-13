"""pack-finance tool logic (spec §12.1): read-only questions about a company's vendor changes.

  vendor_change_path(org, vendor, change)  the path the latest `change` for `vendor` took, and how
                                           it compares with the company's remembered normal path
  approval_history(org, vendor)            who approved each earlier bank-detail change, and how

Both are plain reads through the read-only guard with an explicit timeout and a LIMIT. Both take an
as-of time T; when none is given, T is the time of the newest action in the graph, and the result
says so. Neither writes, and neither calls an LLM. The MCP server in
mcp_servers/pack-finance/server.py only registers these functions.
"""

from core.detectors.bypass import bypass
from core.graph.as_of import run_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import ro_query
from core.takeover import scratch as sc

LATEST_QUERY = (
    "MATCH (a:Action {kind: $change, vendor: $vendor})-[:VIA]->(p:Path) "
    "WHERE a.at <= $T "
    "RETURN a.ref AS ref, a.at AS at, p.channel AS channel, p.callback AS callback, "
    "p.approvers AS approvers ORDER BY a.at DESC, a.ref LIMIT 1"
)
HISTORY_QUERY = (
    "MATCH (a:Action {kind: 'bank_change', vendor: $vendor})-[:VIA]->(p:Path) "
    "WHERE a.at <= $T "
    "OPTIONAL MATCH (k:Actor)-[:APPROVED]->(a) "
    "WITH a, p, collect(k.hid) AS approved_by "
    "RETURN a.ref AS ref, a.at AS at, p.channel AS channel, p.callback AS callback, "
    "p.approvers AS approvers, approved_by ORDER BY at, ref LIMIT 500"
)
NEWEST_QUERY = "MATCH (a:Action) RETURN max(a.at) AS newest LIMIT 1"


def _as_of_time(client: FalkorClient, org: str, T: int | None, timeout_ms: int) -> tuple[int, bool]:
    """(T, defaulted). With no T given, the newest action's time is used."""
    if T is not None:
        return sc.checked_time(T), False
    r = ro_query(client, sc.graph_for(org), NEWEST_QUERY, {}, timeout_ms=timeout_ms)
    newest = r.result_set[0][0] if r.result_set else None
    if newest is None:
        raise ValueError(f"org graph {sc.graph_for(org)} has no actions, so there is no default T")
    return int(newest), True


def vendor_change_path(
    client: FalkorClient,
    org: str,
    vendor: str,
    change: str = "bank_change",
    T: int | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> dict:
    t, defaulted = _as_of_time(client, org, T, timeout_ms)
    rows = run_as_of(
        client,
        sc.graph_for(org),
        LATEST_QUERY,
        {"change": change, "vendor": vendor, "T": t},
        timeout_ms=timeout_ms,
    ).result_set
    out: dict = {"org": org, "vendor": vendor, "change": change, "T": t, "T_defaulted": defaulted}
    if not rows:
        out.update(found=False, reason=f"no '{change}' for this vendor at or before T")
        return out
    ref, at, channel, callback, approvers = rows[0]
    verdict = bypass(client, org, ref, t, timeout_ms)
    out.update(
        found=True,
        action_ref=ref,
        at=at,
        path={"channel": channel, "callback": callback, "approvers": approvers},
        versus_normal={
            "status": verdict.status,
            "reason": verdict.reason,
            "properties": verdict.evidence.get("properties"),
        },
    )
    return out


def approval_history(
    client: FalkorClient,
    org: str,
    vendor: str,
    T: int | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> dict:
    t, defaulted = _as_of_time(client, org, T, timeout_ms)
    rows = run_as_of(
        client,
        sc.graph_for(org),
        HISTORY_QUERY,
        {"vendor": vendor, "T": t},
        timeout_ms=timeout_ms,
    ).result_set
    return {
        "org": org,
        "vendor": vendor,
        "T": t,
        "T_defaulted": defaulted,
        "changes": [
            {
                "action_ref": ref,
                "at": at,
                "channel": channel,
                "callback": callback,
                "approvers_required": approvers,
                "approved_by": sorted(approved_by),
                "approvals_recorded": len(approved_by),
            }
            for ref, at, channel, callback, approvers, approved_by in rows
        ],
    }
