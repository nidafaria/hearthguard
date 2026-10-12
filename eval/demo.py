"""The demo: print the xz replay from saved results only.

Run: python -m eval.demo        (or: make demo)
No network, no key, no graph, no model. It reads the four result files named in
eval/replay_xz.py and prints the table. It writes nothing and prints no time, so every run on the
same files prints the same bytes.
"""

from eval import replay_xz


def main() -> int:
    gone = replay_xz.missing(replay_xz.RESULTS)
    if gone:
        print("Cannot run the demo; missing result files:", ", ".join(gone))
        print("Build them first: see README.md, section 'Commands'.")
        return 1
    print(replay_xz.markdown(replay_xz.build()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
