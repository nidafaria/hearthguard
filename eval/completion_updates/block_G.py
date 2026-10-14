"""Block G re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "README with setup and graph data model": (
        D,
        "README.md: setup (five steps, no key), command table, graph data model as built, queries "
        "and algorithms, measured numbers each with a source file, NOT COMPUTED list, limits, AI "
        "use, tracks; tests/integration/test_incidents_readme.py. The clean-clone question is "
        "row 6 (eval/results/blockers_G.md).",
    ),
    "Live deployment or complete local setup": (
        P,
        "README.md Setup section states the whole local setup (uv, Docker, .env salt, pinned "
        "FalkorDB). No live deployment, and a clean clone still needs the database and the salt "
        "for the full suite (eval/results/blockers_G.md).",
    ),
    "Incident data for event-stream and axios ingested": (
        D,
        "eval/incidents_fetch.py caches the npm registry, OSV and GitHub issue records "
        "(eval/results/incidents_fetch.json); eval/incidents_load.py builds org_event_stream and "
        "org_axios, loaded twice with equal counts and no email-like property "
        "(eval/results/incidents_load.json); tests/integration/test_incidents_load.py. The "
        "removed axios versions' path is from one secondary write-up, labelled secondary.",
    ),
    "OSS pack: parsers for GitHub, npm, mailing lists, bug trackers": (
        D,
        "packs/oss/npm.py (registry packument) and packs/oss/tracker.py (GitHub issue threads) "
        "join the git, GitHub and mail parsers; Debian BTS and Launchpad are in "
        "packs/oss/ecosystem/parse.py; tests/unit/test_oss_parsers_npm.py, "
        "tests/integration/test_incidents_load.py.",
    ),
    "ecosystem_<id> graph": (
        P,
        "Unchanged: packs/oss/ecosystem/graph.py writes Place, Identity, Role, Signal, Decision. "
        "Foundation, HOSTED_BY, Campaign and TOUCHES are not written: no cached public source "
        "names the hosting foundation, and no campaign fired (eval/results/blockers_G.md).",
    ),
    "event-stream and axios replays": (
        D,
        "eval/replay_event_stream.py and eval/replay_axios.py write "
        "eval/results/replay_event_stream.json and replay_axios.json with the frozen detectors "
        "unchanged. event-stream: first NOTE 7.1 days after the malicious release. axios: Bypass "
        "did not fire (33 of 37 releases in the window were manual). Published as measured; "
        "tests/integration/test_incidents_replay.py.",
    ),
    "README, final (claim, commands, model, queries, measured, limits, AI use)": (
        P,
        "README.md has every listed part; there is no demo video link because the video is not "
        "recorded (eval/results/blockers_G.md).",
    ),
}
