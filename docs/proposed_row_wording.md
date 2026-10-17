# Proposed wording for completion rows 11, 34, 55 and 73

For the owner to approve. Nothing in `eval/completion_full.py` or `eval/results/completion_full.md`
was changed. Evidence: `eval/results/xz_grants_from_statements.json`,
`data/derived/xz_grant_statements.json`. Every number comes from those files. All of it is
**from public statements, not a system log, with approximate dates**, computed on a COPY of
`org_xz` (`org_xz_statements`), with the provisional rule `0001-outsider-edges (PROPOSED)`.

The current rows stay as they are (status unchanged) unless you accept a new wording and decide
the status yourself. Proposed status is a suggestion only.

## Row 11, Takeover cost on real xz over time
- Now: NOT STARTED, "NOT COMPUTED (no grant data)".
- Proposed text: "Computed on a copy of org_xz from 5 grant edges taken from public statements (not a
  system log; dates approximate): cost and guardians per `eval/results/xz_grants_from_statements.json`
  at four dates. The real org_xz still has no grant data. Result is provisional (decision 0001)."
- Proposed status: PARTIAL (a result exists, but not from a grant log and not on the real graph).

## Row 34, Privilege, GRANTED, CAN_GRANT, APPROVED
- Now: PARTIAL, "No documented grant records exist for xz".
- Proposed text: "packs/oss/grants.py plus packs/oss/xz_statements.py: 3 GRANTED and 2 CAN_GRANT
  edges from public statements loaded into a copy of org_xz; loading twice gives identical counts
  (tests/integration/test_xz_statements.py). APPROVED comes from the PR review record, not this."
- Proposed status: PARTIAL.

## Row 55, Trust path on real data
- Now: PARTIAL, hard-wired to tallowdate.
- Proposed text: "Not changed by this work. `eval/trust_path_tallowdate.py` was not run on the xz
  copy. The grant edges from statements now exist on a copy, so a trace could be run once the
  script is generalised; that has not been done."
- Proposed status: PARTIAL (no change).

## Row 73, Procedural: remembered normal
- Now: PARTIAL, 3 of 6 metrics computed.
- Proposed text: "3 of 6 metrics computed on xz (xz_normal.json). `grant_days` and
  `trusted_actor_set` could be computed from the statement edges on the copy, but only from public
  statements with approximate dates; this was not run, and `core/normal` was not changed."
- Proposed status: PARTIAL (no change).
