"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

P = "PARTIAL"

UPDATES = {
    "Freeze protocol": (
        P,
        "`make verify-frozen` (eval/verify_frozen.py, Makefile and make.ps1) compares "
        "docs/FREEZE.md to docs/FREEZE.sha256 and reports the status line: the hash matches and "
        "the file still says DRAFT, so it is reported as not frozen (eval/results/"
        "verify_frozen.json); tests/unit/test_verify_frozen.py. Not DONE: the freeze itself and "
        "the public dated copy are the owner's to make; Reader frozen b6e3b1c.",
    ),
}
