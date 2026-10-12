# ruff: noqa: E501 (evidence strings are long by design)
"""Block C re-marks (Red Team, hardening on copies). Read by eval/completion_full.py.

Each entry: row item prefix -> (status, evidence). Reasons for every row that stays open are in
eval/results/blockers_c.md.
"""

D, P = "DONE", "PARTIAL"
UPDATES = {}
