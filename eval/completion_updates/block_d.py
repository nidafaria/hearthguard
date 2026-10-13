"""Block D re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "OSS pack: privileges": (
        D,
        "packs/oss/pack.py (privilege kinds, sensitive flags, normal path, claim vocabulary); "
        "tests/unit/test_pack_oss.py (incl. test_core_imports_nothing_from_packs)",
    ),
    "Action boundary levels 0-2": (
        D,
        "core/policy/boundary.py (levels enum, one check(), Never list); "
        "tests/unit/test_boundary.py (each Never item refused for every recipient; a static scan "
        "finds no outbound write outside the allowed modules). No send path exists yet, so the "
        "scan is the enforcement.",
    ),
    "org graph: Privilege, GRANTED": (
        P,
        "packs/oss/grants.py (documented records -> Privilege, GRANTED, CAN_GRANT, APPROVED); "
        "tests/unit/test_grants_mapping.py, tests/integration/test_grants_write.py. No documented "
        "grant records exist for xz, so its results stay NOT COMPUTED.",
    ),
    "org graph: CONTRADICTS": (
        P,
        "core/claims/conflicts.py writes CONTRADICTS / SUPERSEDES / QUALIFIES via the unchanged "
        "core/policy/conflict.py; tests/integration/test_conflict_links.py. Pairs are supplied "
        "by the caller; no detector finds contradicting pairs yet.",
    ),
    "Semantic claims linked to spans": (
        P,
        "core/claims/conflicts.py (contradictions resolved by policy and linked); "
        "tests/integration/test_conflict_links.py. Pair detection is still missing.",
    ),
    "Who-saw-what memory": (
        P,
        "core/memory/who_saw.py (PARTICIPATES_IN, WATCHES {since}, already_acknowledged); "
        "tests/integration/test_who_saw.py. Not yet filled from the cached mail and git data.",
    ),
    "Trust path query": (
        P,
        "core/takeover/trust_path.py (SPpaths, tested in tests/integration/test_trust_path.py); "
        "eval/results/trust_path_tallowdate.json: NOT COMPUTED for every quarter, because the "
        "tallowdate case records no grant.",
    ),
}
