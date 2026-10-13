"""(:Hardening) nodes in the org graph (docs/HEARTHGUARD.md 6.1).

One node per (run_ref, step), written with MERGE so replaying a run writes nothing twice. The
numbers are whatever the hardening replay measured; this module only stores them. No LLM.

  (:Hardening {step, cost_before, cost_after, guardians_before, guardians_after, caught_before,
               caught_after, lead_before, lead_after, run_ref})-[:FOR]->(:Org)
"""

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient

FIELDS = (
    "cost_before",
    "cost_after",
    "guardians_before",
    "guardians_after",
    "caught_before",
    "caught_after",
    "lead_before",
    "lead_after",
)


def record_hardening(
    client: FalkorClient,
    graph: str,
    org: str,
    run_ref: str,
    step: str,
    numbers: dict,
    *,
    synthetic: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """MERGE one hardening step. `numbers` holds the FIELDS (any may be None). True if new."""
    unknown = set(numbers) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown hardening fields: {sorted(unknown)}")
    params = {f: numbers.get(f) for f in FIELDS}
    params.update(org=org, run_ref=run_ref, step=step, synthetic=synthetic)
    sets = ", ".join(f"h.{f} = ${f}" for f in FIELDS)
    r = client.query(
        graph,
        "MERGE (h:Hardening {run_ref: $run_ref, step: $step}) "
        f"ON CREATE SET {sets}, h.synthetic = $synthetic",
        params,
        timeout_ms=timeout_ms,
    )
    client.query(
        graph,
        "MERGE (o:Org {id: $org}) "
        "WITH o MATCH (h:Hardening {run_ref: $run_ref, step: $step}) MERGE (h)-[:FOR]->(o)",
        params,
        timeout_ms=timeout_ms,
    )
    return r.nodes_created > 0


def hardening_steps(
    client: FalkorClient, graph: str, run_ref: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> list[dict]:
    r = client.query(
        graph,
        "MATCH (h:Hardening {run_ref: $run_ref})-[:FOR]->(:Org) RETURN h ORDER BY h.step",
        {"run_ref": run_ref},
        timeout_ms=timeout_ms,
    )
    return [dict(row[0].properties) for row in r.result_set]
