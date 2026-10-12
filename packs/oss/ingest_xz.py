"""Ingest the public xz git history into org_xz. Run: python -m packs.oss.ingest_xz [--twice]

--twice runs the load two times over the same parsed input and checks that the node and edge
counts do not change (idempotency). Counts are printed before and after each run.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from core.graph.client import FalkorClient
from packs.oss import git_ingest, xz_graph

RESULTS = git_ingest.REPO_ROOT / "eval" / "results"


def _gap(question: str, why: str, later: str) -> dict:
    return {"question": question, "why_git_cannot_say": why, "possible_later_source": later}


# What a git history cannot tell us about trust. Nothing here is a claim about any person.
GRANTS_UNKNOWN = {
    "source": "git history only (packs/oss/git_ingest.py)",
    "summary": (
        "Git records who authored commits and who made tags. It has no record of who was given "
        "which rights, by whom, or when. No Privilege node and no GRANTED or CAN_GRANT edge was "
        "written. Grant edges come later from maintainer history."
    ),
    "git_cannot_tell_us": [
        _gap(
            "Who holds merge, release, signing and publishing rights, and since when?",
            "Push and release rights are server and project settings, not commit data.",
            "Maintainer announcements and project documentation.",
        ),
        _gap(
            "Who approved or granted a right to whom?",
            "A commit has an author and a committer, not an approver or a grantor.",
            "Mailing-list and tracker records of the handover.",
        ),
        _gap(
            "Did an author have commit access, or was the patch applied by someone else?",
            "Author and committer can differ. This ingest keeps the author only.",
            "The committer field, plus the grant history above.",
        ),
        _gap(
            "Do release tag signatures check out?",
            "Checking a signature needs the signer's public key, which git history does not hold.",
            "Public keys published by the project, checked on a throw-away keyring.",
        ),
        _gap(
            "Which channel did a release really use (CI, provenance, tarball builder)?",
            "Release tarballs are built outside git. The backdoor was in release tarballs, "
            "not in the git history.",
            "Release artifacts and their published checksums.",
        ),
    ],
}


def _print_counts(label: str, counts: dict) -> None:
    print(f"[{label}] nodes={json.dumps(counts['nodes'], sort_keys=True)}")
    print(f"[{label}] edges={json.dumps(counts['edges'], sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--twice", action="store_true", help="load twice and compare the counts")
    ap.add_argument("--export", type=Path, help="write a JSON dump of the graph (for grep checks)")
    args = ap.parse_args(argv)

    info = git_ingest.ensure_mirror()
    print(
        f"source={info['source_url']} head={info['head_sha']} "
        f"fetched_at={info['fetched_at_utc']} cached={info['cached']}"
    )
    mirror = git_ingest.RAW_DIR / "xz.git"
    tags = git_ingest.read_tags(mirror)
    commits = git_ingest.read_commits(mirror, {t["target_sha"] for t in tags})
    annotated = [t["name"] for t in tags if t["kind"] == "annotated"]
    signatures = git_ingest.verify_tags(mirror, annotated)
    print(
        f"parsed commits={len(commits)} authors={len({c['hid'] for c in commits})} "
        f"tags={len(tags)} annotated={len(annotated)} "
        f"signatures={dict(Counter(s['state'] for s in signatures.values()))}"
    )

    client = FalkorClient()
    before = xz_graph.graph_counts(client) if _graph_exists(client) else {"nodes": {}, "edges": {}}
    _print_counts("before", before)
    xz_graph.load(client, commits, tags, signatures)
    after1 = xz_graph.graph_counts(client)
    _print_counts("after run 1", after1)
    after2 = None
    if args.twice:
        xz_graph.load(client, commits, tags, signatures)
        after2 = xz_graph.graph_counts(client)
        _print_counts("after run 2", after2)
        if after2 != after1:
            print("FAIL: counts changed on the second run", file=sys.stderr)
            return 1
        print("OK: counts identical after the second run")

    at_hits = xz_graph.scan_for_at_sign(client)
    print(f"'@' scan of the graph: {len(at_hits)} hit(s) {at_hits}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "xz_grants_unknown.json").write_text(
        json.dumps(GRANTS_UNKNOWN, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "source_url": info["source_url"],
        "head_sha": info["head_sha"],
        "fetched_at_utc": info["fetched_at_utc"],
        "time_unit": "Unix epoch seconds, UTC",
        "parsed": {
            "commits": len(commits),
            "distinct_author_hids": len({c["hid"] for c in commits}),
            "merge_commits": sum(c["n_parents"] > 1 for c in commits),
            "annotated_tags": len(annotated),
            "lightweight_tags": [t["name"] for t in tags if t["kind"] == "lightweight"],
        },
        "signature_states": dict(Counter(s["state"] for s in signatures.values())),
        "verified_note": (
            "Path.verified is true only for a signature that checks out. The check ran on a "
            "throw-away copy with an empty keyring, so present signatures report no_public_key "
            "and verified=false."
        ),
        "counts_after_run_1": after1,
        "counts_after_run_2": after2,
        "idempotent": (after2 == after1) if after2 is not None else None,
        "at_sign_hits": at_hits,
        "note": (
            "This is the public git history only. The xz backdoor was in release tarballs, "
            "not in the git history, so nothing here shows the backdoor."
        ),
    }
    (RESULTS / "xz_ingest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.export:
        _export(client, args.export)
        print(f"graph export written to {args.export}")
    return 1 if at_hits else 0


def _graph_exists(client: FalkorClient) -> bool:
    return xz_graph.GRAPH.encode() in {
        g if isinstance(g, bytes) else g.encode() for g in client.db.execute_command("GRAPH.LIST")
    }


def _export(client: FalkorClient, path: Path) -> None:
    nodes = client.query(xz_graph.GRAPH, "MATCH (n) RETURN n", timeout_ms=60_000).result_set
    edges = client.query(
        xz_graph.GRAPH, "MATCH (a)-[r]->(b) RETURN r, a.hid, a.ref, b.hid, b.ref", timeout_ms=60_000
    ).result_set
    dump = {
        "nodes": [{"labels": n.labels, "properties": n.properties} for (n,) in nodes],
        "edges": [
            {"type": r.relation, "properties": r.properties, "from": [ah, aref], "to": [bh, bref]}
            for r, ah, aref, bh, bref in edges
        ],
    }
    path.write_text(json.dumps(dump, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
