"""AgentStep: the working-memory log (docs/HEARTHGUARD.md 8.2, 9).

Every tool call an agent makes for a task is one (:AgentStep) hung on the task. The log is in the
graph, so when an agent crashes and its lease runs out, the next agent that claims the task reads
the steps and carries on. No LLM here; llm_calls is a count the caller reports.

  (:Task)-[:STEP]->(:AgentStep {id, seq, agent, tool, reason, ms, result_ref, llm_calls, at})
"""

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient


def log_step(
    client: FalkorClient,
    graph: str,
    task_id: str,
    agent: str,
    tool: str,
    reason: str,
    ms: float,
    result_ref: str | None,
    llm_calls: int,
    at: int,
    *,
    synthetic: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> int | None:
    """Append a step. The sequence number is counted in the same query that writes the step, so
    two agents logging at once get different numbers. None if the task does not exist."""
    r = client.query(
        graph,
        "MATCH (t:Task {id: $tid}) "
        "OPTIONAL MATCH (t)-[:STEP]->(s:AgentStep) "
        "WITH t, count(s) AS n "
        "MERGE (t)-[:STEP]->(x:AgentStep {id: $tid + ':' + toString(n)}) "
        "ON CREATE SET x.seq = n, x.agent = $agent, x.tool = $tool, x.reason = $reason, "
        "x.ms = $ms, x.result_ref = $ref, x.llm_calls = $llm, x.at = $at, "
        "x.synthetic = $synthetic "
        "RETURN x.seq",
        {
            "tid": task_id,
            "agent": agent,
            "tool": tool,
            "reason": reason,
            "ms": ms,
            "ref": result_ref,
            "llm": llm_calls,
            "at": at,
            "synthetic": synthetic,
        },
        timeout_ms=timeout_ms,
    )
    return r.result_set[0][0] if r.result_set else None


def steps_for(
    client: FalkorClient, graph: str, task_id: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> list[dict]:
    r = client.query(
        graph,
        "MATCH (:Task {id: $tid})-[:STEP]->(s:AgentStep) RETURN s ORDER BY s.seq",
        {"tid": task_id},
        timeout_ms=timeout_ms,
    )
    return [dict(row[0].properties) for row in r.result_set]


def resume_state(
    client: FalkorClient, graph: str, task_id: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> dict:
    """What a second agent needs to continue a task: the steps so far, which tools already ran
    with a stored result, and how many LLM calls the task has used."""
    steps = steps_for(client, graph, task_id, timeout_ms)
    return {
        "task_id": task_id,
        "steps": steps,
        "tools_done": [s["tool"] for s in steps if s.get("result_ref")],
        "llm_calls": sum(s.get("llm_calls") or 0 for s in steps),
        "last_agent": steps[-1]["agent"] if steps else None,
    }
