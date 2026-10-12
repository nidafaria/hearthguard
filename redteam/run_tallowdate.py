"""Run the tallowdate pipeline, steps 1 to 5, in order. Run: make tallowdate-run.

Prints PASS or FAIL per step and the files it wrote. On a failure the run stops, and the last
lines of that step's error output are shown. Each step runs as its own module.
"""

import os
import subprocess
import sys

STEPS = [
    ("1 load", ["redteam.load_tallowdate", "--twice"], ["eval/results/tallowdate_load.json"]),
    ("2 normal", ["redteam.tallowdate_normal"], ["eval/results/tallowdate_normal.json"]),
    (
        "3 detectors",
        ["redteam.tallowdate_detectors"],
        ["eval/results/tallowdate_detector_status.json"],
    ),
    ("4 decision", ["redteam.tallowdate_decision"], ["eval/results/tallowdate_decision.json"]),
    (
        "5 demo script",
        ["redteam.tallowdate_demo_script"],
        ["eval/results/tallowdate_demo_script.json"],
    ),
]


def main() -> int:
    for name, module, outputs in STEPS:
        env = {**os.environ, "PYTHONUTF8": "1"}  # a child's console text must not break this run
        proc = subprocess.run(
            [sys.executable, "-m", *module],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if proc.returncode != 0:
            print(f"FAIL {name}")
            for line in (proc.stderr or proc.stdout).strip().splitlines()[-3:]:
                print(f"    {line}")
            return proc.returncode
        print(f"PASS {name}")
        for path in outputs:
            print(f"    wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
