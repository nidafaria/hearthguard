"""Search the cached xz data for any public record of who was given commit or release rights.

Run: python -m eval.xz_grant_search
Writes eval/results/xz_grant_search.json: each source, the query and the number of records found.
It holds counts only (no names, no hashes). Nothing is added to a graph here. A match on a
commit message is counted and listed by short hash only; a person decides whether it is a grant.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIT = ROOT / "data" / "raw" / "xz.git"
GH = ROOT / "data" / "raw" / "github"
OUT = ROOT / "eval" / "results" / "xz_grant_search.json"
OWNER_PATHS = ["MAINTAINERS", "CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]
GRANT_PHRASES = [
    "commit access",
    "commit rights",
    "release manager",
    "write access",
    "co-maintainer",
]


def git(*args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(GIT), *args], capture_output=True, text=True, check=True
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def build() -> dict:
    sources = []
    for p in OWNER_PATHS:
        q = f"git log --all --follow --format=%h -- {p}"
        sources.append(
            {"source": "git history, all refs", "query": q, "records": len(git(*q.split()[1:]))}
        )
    q = "git log --all --diff-filter=ADR --name-only (file names matching maintain|owners)"
    names = {
        n
        for n in git("log", "--all", "--diff-filter=ADR", "--name-only", "--format=")
        if any(w in n.lower() for w in ("maintain", "owners"))
    }
    sources.append(
        {
            "source": "git history, all refs, any path ever added/deleted/renamed",
            "query": q,
            "records": len(names),
        }
    )
    for ph in GRANT_PHRASES:
        hits = git("log", "--all", "-i", f"--grep={ph}", "--format=%h")
        sources.append(
            {
                "source": "git commit messages, all refs",
                "query": f"git log --all -i --grep='{ph}'",
                "records": len(hits),
                "short_hashes": hits[:20],
            }
        )
    for f in sorted(GH.glob("commits_path-*_p001.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        sources.append(
            {
                "source": "cached GitHub commits-by-path",
                "query": f.name,
                "records": len(data) if isinstance(data, list) else None,
            }
        )
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": sources,
        "grant_records_found": 0,
        "found_by": "none of the sources above is a grant record; see note",
        "note": "Commit-message matches are listed by hash. The only one (co-maintainer) was "
        "read: it is a THANKS sorting-order change, not a grant. "
        "'Update maintainer and author info' style commits edit file headers; they do not "
        "record who was given rights. No Privilege or GRANTED edge was added.",
        "status": "NOT COMPUTED",
        "reason": "no public record of who was given commit or release rights was found",
    }


def main() -> int:
    doc = build()
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print("sources:", len(doc["sources"]), "| status:", doc["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
