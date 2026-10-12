# ruff: noqa: E501 (evidence strings are long by design)
"""Block C re-marks (Red Team, hardening on copies). Read by eval/completion_full.py.

Each entry: row item prefix -> (status, evidence). Reasons for every row that stays open are in
eval/results/blockers_c.md. Evidence files are measured on a campaign planted into a COPY: the
xz results are labelled "campaign planted into a copy of public xz history; not a finding about
xz" and the tallowdate results "SYNTHETIC".
"""

D, P = "DONE", "PARTIAL"
UPDATES = {
    "Red Team generator": (
        D,
        "redteam/generate.py (N, SEED, patience, moves, privilege; same seed same bytes); "
        "tests/unit/test_redteam_generate.py; tests/integration/test_redteam.py; "
        "eval/results/redteam_tallowdate.json",
    ),
    "redteam_<run> and harden_<run> graphs": (
        D,
        "redteam/run.py and redteam/harden.py GRAPH.COPY org_tallowdate and org_xz to redteam_<run> "
        "and harden_<run>, plant into the copy only; tests/integration/test_redteam.py; "
        "eval/results/redteam_tallowdate.json, redteam_xz.json (real graph counts before and after)",
    ),
    "Hardening simulator (up to three steps, measured)": (
        D,
        "redteam/harden.py: three menu steps, same campaigns, frozen detectors, caught and lead "
        "time before/after; eval/results/hardening_redteam_tallowdate.json, hardening_redteam_xz.json; "
        "tests/integration/test_redteam.py",
    ),
    "Hardening on xz and 10 false-alarm projects": (
        P,
        "xz half done: `make harden CASE=xz` writes eval/results/hardening_redteam_xz.json "
        "(planted campaigns, copy of org_xz). The 10 false-alarm projects are not in the repo and "
        "are not invented; blockers_c.md",
    ),
    "`make redteam N=200 SEED=...`": (
        D,
        "Makefile and make.ps1 target redteam (N, SEED, CASE); eval/results/redteam_tallowdate.json "
        "(seed 7, N 200), eval/results/redteam_xz.json",
    ),
}
