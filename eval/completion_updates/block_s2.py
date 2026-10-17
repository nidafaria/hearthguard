"""s2 re-marks, applied by eval/completion_full.py. Wording from docs/proposed_row_wording.md.

Nothing here is DONE. Grant data is from public statements, not a system log; dates approximate.
"""

P = "PARTIAL"

UPDATES = {
    "Takeover cost on real xz": (
        P,
        "Computed on a copy of org_xz from 5 grant edges taken from public statements (not a "
        "system log; dates approximate): cost and guardians per "
        "eval/results/xz_grants_from_statements.json at four dates. The real org_xz still has no "
        "grant data. Result is provisional (decision 0001).",
    ),
    "org graph: Privilege, GRANTED": (
        P,
        "packs/oss/grants.py plus packs/oss/xz_statements.py: 3 GRANTED and 2 CAN_GRANT edges "
        "from public statements loaded into a copy of org_xz; loading twice gives identical "
        "counts (tests/integration/test_xz_statements.py). APPROVED comes from the PR review "
        "record, not this.",
    ),
    "Trust path query": (
        P,
        "Not changed by this work. `eval/trust_path_tallowdate.py` was not run on the xz copy. "
        "The grant edges from statements now exist on a copy, so a trace could be run once the "
        "script is generalised; that has not been done.",
    ),
    "Procedural: remembered normal": (
        P,
        "3 of 6 metrics computed on xz (xz_normal.json). `grant_days` and `trusted_actor_set` "
        "could be computed from the statement edges on the copy, but only from public statements "
        "with approximate dates; this was not run, and `core/normal` was not changed.",
    ),
}
