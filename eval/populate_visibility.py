"""Fill the visibility graph (spec §6.1, §9) from the cached xz mail and git data.

Run: uv run python -m eval.populate_visibility [--graph org_xz_visibility] [--git]

Reads, writes nothing outside the named graph:
  mail  data/raw/mail/xz-devel/index.json (public mail-archive pages, author already hashed)
  git   the xz mirror under data/raw/xz.git, only with --git (author emails are hashed on read,
        which needs HEARTHGUARD_HASH_SALT; without it the git part is skipped and says so)

Writes, all through core/memory/who_saw.py and all idempotent (a second run changes no count):
  (:Place {ref, kind})                         the list `mail:xz-devel`, the repo `git:xz`
  (:Actor)-[:PARTICIPATES_IN {since, last_at}]->(:Place)
  (:Action)-[:RECORDED_IN]->(:Place)           every mail message and every commit
Mail messages are written as Action{kind:'email'} with a DID edge from their author, so the edge
has something to hang on. Commits are not re-created: a commit is linked only if its Action
already exists in the graph (org_xz has them; a fresh graph does not, and the count says so).

Writes eval/results/visibility_xz.json (counts only; no name, no email).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.graph.hashing import MissingSaltError
from core.graph.schema import apply_schema
from core.memory import who_saw

ROOT = Path(__file__).resolve().parents[1]
MAIL_INDEX = ROOT / "data" / "raw" / "mail" / "xz-devel" / "index.json"
RESULT = ROOT / "eval" / "results" / "visibility_xz.json"
MAIL_PLACE = {"ref": "mail:xz-devel", "kind": "list"}
GIT_PLACE = {"ref": "git:xz", "kind": "repo"}
TIMEOUT = 60_000
BATCH = 500


def epoch(date_utc: str) -> int:
    return int(datetime.fromisoformat(date_utc.replace("Z", "+00:00")).timestamp())


def mail_events(index: dict) -> list[dict]:
    """One event per cached message that has a date and a hashed author."""
    out = []
    for m in index["messages"]:
        if m.get("status") != 200 or not m.get("author_hash") or not m.get("date_utc"):
            continue
        out.append(
            {
                "ref": f"xz-devel:msg{m['msg']:05d}",
                "hid": m["author_hash"],
                "place": MAIL_PLACE["ref"],
                "at": epoch(m["date_utc"]),
            }
        )
    return out


def git_events(commits: list[dict]) -> list[dict]:
    return [
        {"ref": c["sha"], "hid": c["hid"], "place": GIT_PLACE["ref"], "at": c["at"]}
        for c in commits
    ]


def _chunks(rows: list[dict]):
    for i in range(0, len(rows), BATCH):
        yield rows[i : i + BATCH]


def write_mail_actions(client: FalkorClient, graph: str, events: list[dict]) -> None:
    for batch in _chunks(events):
        client.query(
            graph,
            "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) "
            "MERGE (x:Action {ref: r.ref}) SET x.kind = 'email', x.at = r.at "
            "MERGE (a)-[d:DID]->(x) SET d.at = r.at",
            {"rows": batch},
            timeout_ms=TIMEOUT,
        )


def populate(
    client: FalkorClient, graph: str, mail: list[dict], git: list[dict] | None = None
) -> dict:
    """Write places, participation and RECORDED_IN. Returns counts read back from the graph."""
    apply_schema(client, graph)
    git = git or []
    who_saw.write_places(client, graph, [MAIL_PLACE, *([GIT_PLACE] if git else [])])
    write_mail_actions(client, graph, mail)
    events = mail + git
    rows = who_saw.participation_rows(events)
    for batch in _chunks(rows):
        who_saw.write_participation(client, graph, batch)
    for batch in _chunks([{"ref": e["ref"], "place": e["place"]} for e in events]):
        who_saw.write_recorded_in(client, graph, batch)
    return counts(client, graph)


def counts(client: FalkorClient, graph: str) -> dict:
    def one(cypher: str) -> int:
        return client.query(graph, cypher, timeout_ms=TIMEOUT).result_set[0][0]

    return {
        "places": one("MATCH (p:Place) RETURN count(p)"),
        "participates_in": one("MATCH ()-[e:PARTICIPATES_IN]->() RETURN count(e)"),
        "recorded_in": one("MATCH ()-[e:RECORDED_IN]->() RETURN count(e)"),
        "actors": one("MATCH (a:Actor) RETURN count(a)"),
        "actions": one("MATCH (x:Action) RETURN count(x)"),
    }


def read_git_events(mirror: Path | None = None) -> list[dict]:
    """Commits from the cached mirror. Needs the hashing salt; raises MissingSaltError without."""
    from packs.oss import git_ingest

    mirror = mirror or git_ingest.RAW_DIR / "xz.git"
    tags = git_ingest.read_tags(mirror)
    commits = git_ingest.read_commits(mirror, {t["target_sha"] for t in tags})
    return git_events(commits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="org_xz_visibility")
    ap.add_argument("--git", action="store_true", help="also read the cached git mirror")
    ap.add_argument("--mirror", default=None, help="path of the cached xz.git mirror")
    ap.add_argument("--mail-index", default=str(MAIL_INDEX))
    ap.add_argument("--out", default=str(RESULT))
    args = ap.parse_args(argv)

    index = json.loads(Path(args.mail_index).read_text(encoding="utf-8"))
    mail = mail_events(index)
    git: list[dict] = []
    git_status = "not requested"
    if args.git:
        try:
            git = read_git_events(Path(args.mirror) if args.mirror else None)
            git_status = f"read {len(git)} commits"
        except MissingSaltError as e:
            git_status = f"skipped: {e}"
    client = FalkorClient()
    first = populate(client, args.graph, mail, git)
    second = populate(client, args.graph, mail, git)
    out = {
        "graph": args.graph,
        "mail_messages_read": len(mail),
        "git": git_status,
        "git_commits_read": len(git),
        "counts_after_first_run": first,
        "counts_after_second_run": second,
        "idempotent": first == second,
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["idempotent"] else 1


if __name__ == "__main__":
    sys.exit(main())
