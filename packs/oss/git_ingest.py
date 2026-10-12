"""Parse the public xz git history into plain dicts. No graph writes happen here.

Privacy (docs/HEARTHGUARD.md §4.5 rules 7 and 8): author and tagger emails are hashed on the way
in and never stored. Author names are used in memory only, to recognise the already-public,
adjudicated persona "Jia Tan" (GitHub JiaT75). No other name or email leaves this module.

Times are Unix epoch seconds (UTC), so `at` and the as-of T compare as plain integers.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from core.graph.hashing import identifier_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"

# Tried in this order. The first one that answers `git ls-remote` is used.
SOURCES = (
    "https://git.tukaani.org/xz.git",
    "https://github.com/tukaani-project/xz.git",
)

# git author name (compared in lowercase, never stored) -> public handle. §4.5 rule 7: only
# already-public, adjudicated historical personas are named.
PUBLIC_PERSONAS = {"jia tan": "JiaT75"}

_RS = "\x1e"  # record separator
_US = "\x1f"  # unit separator


class SourceUnavailable(RuntimeError):
    """No public xz git source answered. Do not continue with a substitute source."""


def _git(git_dir: Path | None, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = ["git"]
    if git_dir is not None:
        cmd += ["--git-dir", str(git_dir)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, env=env, check=False)


def _text(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_mirror(raw_dir: Path = RAW_DIR) -> dict:
    """Return fetch info for the cached bare mirror, cloning it first if it is not cached."""
    mirror = raw_dir / "xz.git"
    fetch_json = raw_dir / "xz.fetch.json"
    if mirror.is_dir() and fetch_json.is_file():
        info = json.loads(fetch_json.read_text(encoding="utf-8"))
        info["cached"] = True
        return info
    if mirror.exists():
        raise RuntimeError(f"{mirror} exists without {fetch_json.name}; delete it and re-run")

    raw_dir.mkdir(parents=True, exist_ok=True)
    for url in SOURCES:
        probe = _git(None, "ls-remote", url, "HEAD")
        if probe.returncode != 0 or not probe.stdout.strip():
            continue
        clone = _git(None, "clone", "--mirror", url, str(mirror))
        if clone.returncode != 0:
            shutil.rmtree(mirror, ignore_errors=True)
            raise RuntimeError(f"git clone --mirror failed for {url}: {_text(clone.stderr)[:300]}")
        head = _text(_git(mirror, "rev-parse", "HEAD").stdout).strip()
        info = {"source_url": url, "fetched_at_utc": _utc_now(), "head_sha": head}
        fetch_json.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        info["cached"] = False
        return info
    raise SourceUnavailable("none of the public xz git sources resolved: " + ", ".join(SOURCES))


def hash_email(email: str) -> str:
    """Salted hash of a lowercased email. The email itself is never kept."""
    return identifier_hash(email.strip().lower())


def parse_shortstat(text: str) -> int:
    """Files touched, from a `git log --shortstat` block. No stat line means no changed files."""
    m = re.search(r"(\d+) files? changed", text)
    return int(m.group(1)) if m else 0


def read_tags(mirror: Path) -> list[dict]:
    """Every tag as a dict. Annotated tags have a tagger time and hashed tagger; others do not."""
    fmt = _US.join(
        [
            "%(refname:short)",
            "%(objecttype)",
            "%(*objecttype)",
            "%(*objectname)",
            "%(objectname)",
            "%(taggerdate:unix)",
            "%(taggeremail)",
        ]
    )
    out = _git(mirror, "for-each-ref", "refs/tags", f"--format={fmt}")
    if out.returncode != 0:
        raise RuntimeError(f"git for-each-ref failed: {_text(out.stderr)[:300]}")
    tags = []
    for line in _text(out.stdout).splitlines():
        name, otype, target_type, target_sha, own_sha, tagger_at, tagger_email = line.split(_US)
        if otype == "tag":
            tags.append(
                {
                    "name": name,
                    "kind": "annotated",
                    "target_type": target_type,
                    "target_sha": target_sha,
                    "at": int(tagger_at),
                    "tagger_hid": hash_email(tagger_email.strip("<>")) if tagger_email else None,
                }
            )
        else:
            tags.append(
                {
                    "name": name,
                    "kind": "lightweight",
                    "target_type": otype,
                    "target_sha": own_sha,
                    "at": None,
                    "tagger_hid": None,
                }
            )
    tags.sort(key=lambda t: t["name"])
    return tags


def read_commits(mirror: Path, tag_targets: set[str]) -> list[dict]:
    """Every commit on every ref: hashed author, author time, files touched, release-target flag.

    Merge commits are measured against their first parent, so files_touched is the size of what
    the merge brought in. Author time is the author date, which can differ from commit order.
    """
    fmt = f"{_RS}%H{_US}%at{_US}%ae{_US}%an{_US}%P"
    out = _git(
        mirror, "log", "--all", "--diff-merges=first-parent", "--shortstat", f"--format={fmt}"
    )
    if out.returncode != 0:
        raise RuntimeError(f"git log failed: {_text(out.stderr)[:300]}")
    commits = []
    for record in _text(out.stdout).split(_RS):
        if not record.strip():
            continue
        header, _, rest = record.partition("\n")
        sha, at, email, name, parents = header.split(_US)
        commit = {
            "sha": sha,
            "at": int(at),
            "hid": hash_email(email),
            "files_touched": parse_shortstat(rest),
            "release_target": sha in tag_targets,
            "n_parents": len(parents.split()),
        }
        handle = PUBLIC_PERSONAS.get(name.strip().lower())
        if handle:
            commit["handle_public"] = handle  # present only for the public persona
        commits.append(commit)
    commits.sort(key=lambda c: (c["at"], c["sha"]))
    return commits


def classify_signature(has_block: bool, raw_status: str) -> str:
    """Map `git verify-tag --raw` GnuPG status lines to a short state."""
    if not has_block:
        return "unsigned"
    tokens = {
        line.split()[1]
        for line in raw_status.splitlines()
        if line.startswith("[GNUPG:] ") and len(line.split()) > 1
    }
    if "BADSIG" in tokens:
        return "bad"
    if "GOODSIG" in tokens or "VALIDSIG" in tokens:
        return "good"
    if tokens & {"EXPKEYSIG", "REVKEYSIG", "EXPSIG"}:
        return "key_expired_or_revoked"
    if "NO_PUBKEY" in tokens:
        return "no_public_key"
    return "error"


def verify_tags(mirror: Path, names: list[str]) -> dict[str, dict]:
    """Check each annotated tag's signature on a throw-away copy, with an empty keyring.

    With no public keys imported, a present signature cannot be checked: its state is
    'no_public_key' and verified is False. verified is True only for a signature that checks out.
    """
    result: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.git"
        shutil.copytree(mirror, copy)
        gnupg_home = Path(tmp) / "gnupg"
        gnupg_home.mkdir()
        env = {**os.environ, "GNUPGHOME": str(gnupg_home)}
        for name in names:
            body = _text(_git(copy, "cat-file", "-p", f"refs/tags/{name}").stdout)
            has_block = "BEGIN PGP SIGNATURE" in body or "BEGIN SSH SIGNATURE" in body
            raw = ""
            if has_block:
                raw = _text(_git(copy, "verify-tag", "--raw", name, env=env).stderr)
            state = classify_signature(has_block, raw)
            result[name] = {"state": state, "verified": state == "good"}
    return result
