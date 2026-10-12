"""Freeze the Reader before anyone labels, so the test set can only test THIS prompt.

Run:  python -m eval.reader_freeze                         create version 1, or verify it
      python -m eval.reader_freeze --new-version --reason "why"
                                                           log a change as a new version (this makes
                                                           any labelled test invalid; see below)

eval/results/reader_frozen.json records SHA-256 hashes of what decides the Reader's behaviour:
  - the system prompt text
  - the user prompt template (rendered with a fixed stand-in message)
  - the JSON schema the reply must satisfy
  - config/models.yaml (model ids, base URL, limits)
  - the call parameters (model, temperature, output cap, quote-length limit, validation rule)
and, for information only, the hash of core/claims/reader.py and the git commit.
What the Reader is shown is also pinned: eval/results/reader_testset.json records a hash of each
cleaned message text, and the scorer refuses to run if one has changed.

Changing any frozen component after labels exist makes the test invalid. The change must be logged
here as a new version, with a reason, and the labels must be treated as belonging to the old one.
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.claims import reader
from core.llm.client import REPO_ROOT, load_config, strict_schema

RESULTS = Path(__file__).resolve().parent / "results"
FROZEN_PATH = RESULTS / "reader_frozen.json"
LABELSHEET_PATH = RESULTS / "reader_labelsheet.csv"
MODELS_YAML = REPO_ROOT / "config" / "models.yaml"
READER_SOURCE = REPO_ROOT / "core" / "claims" / "reader.py"

STAND_IN_MESSAGE = "<<MESSAGE>>"
STAND_IN_AUTHOR = "<<AUTHOR_HASH>>"
FROZEN_COMPONENTS = (
    "system_prompt_sha256",
    "user_template_sha256",
    "schema_sha256",
    "models_yaml_sha256",
    "parameters_sha256",
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parameters() -> dict:
    """Everything else that shapes a Reader call. The reasoning effort is not set by the client."""
    return {
        "model": load_config()["extraction_model"],
        "temperature": 0,
        "max_completion_tokens": reader.MAX_TOKENS,
        "max_quote_words": reader.MAX_QUOTE_WORDS,
        "reasoning_effort": "not set (the model's default)",
        "response_format": "json_schema, strict",
        "validation": "pydantic strict; a claim is kept only if its quote is an exact substring",
    }


def current_components() -> dict:
    system, user = reader.build_prompt(STAND_IN_MESSAGE, STAND_IN_AUTHOR)
    schema = json.dumps(strict_schema(reader.ReaderReply), sort_keys=True, separators=(",", ":"))
    params = parameters()
    return {
        "system_prompt_sha256": sha256_text(system),
        "user_template_sha256": sha256_text(user),
        "schema_sha256": sha256_text(schema),
        "models_yaml_sha256": hashlib.sha256(MODELS_YAML.read_bytes()).hexdigest(),
        "parameters_sha256": sha256_text(json.dumps(params, sort_keys=True)),
    }


def git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def labels_exist(path: Path | None = None) -> bool:
    """True if a person has filled in any label cell on the sheet."""
    path = path or LABELSHEET_PATH
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if any((row.get(k) or "").strip() for k in reader_kinds()):
                return True
    return False


def reader_kinds() -> list[str]:
    return [k.value for k in reader.ClaimKind if k is not reader.ClaimKind.NONE]


def build_version(version: int) -> dict:
    return {
        "version": version,
        "frozen_at_utc": now_utc(),
        "git_head_when_frozen": git_head(),
        "components": current_components(),
        "parameters": parameters(),
        "reader_source_sha256_informational": hashlib.sha256(
            READER_SOURCE.read_bytes()
        ).hexdigest(),
    }


def load_frozen(path: Path = FROZEN_PATH) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def mismatches(frozen: dict) -> list[str]:
    """Names of frozen components that differ from the code and config as they are now."""
    now = current_components()
    return [name for name in FROZEN_COMPONENTS if frozen["components"][name] != now[name]]


def create(path: Path = FROZEN_PATH) -> dict:
    doc = {
        **build_version(1),
        "note": (
            "Frozen before any labelling. A later change to any component makes the labelled "
            "test invalid and must be logged as a new version in `history`."
        ),
        "history": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def new_version(reason: str, path: Path = FROZEN_PATH, labels: bool | None = None) -> dict:
    """Log the current code and config as the next version, keeping the old one in `history`."""
    if not reason.strip():
        raise ValueError("a new version needs a reason")
    old = load_frozen(path)
    if old is None:
        raise ValueError("nothing is frozen yet")
    had_labels = labels_exist() if labels is None else labels
    retired = {k: v for k, v in old.items() if k != "history"}
    retired["retired_at_utc"] = now_utc()
    retired["retired_because"] = reason.strip()
    retired["labels_existed_when_retired"] = had_labels
    doc = {**build_version(old["version"] + 1), "note": old["note"]}
    doc["history"] = [*old["history"], retired]
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-version", action="store_true")
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)

    frozen = load_frozen()
    if args.new_version:
        doc = new_version(args.reason)
        warn = (
            " Labels already exist: the old version's labelled test is no longer valid."
            if doc["history"][-1]["labels_existed_when_retired"]
            else ""
        )
        print(f"logged version {doc['version']}.{warn}")
        return 0
    if frozen is None:
        doc = create()
        print(f"froze version 1 at {doc['frozen_at_utc']}")
        return 0
    bad = mismatches(frozen)
    if bad:
        print(f"NOT FROZEN: these differ from version {frozen['version']}: {', '.join(bad)}")
        print(
            'Log the change with --new-version --reason "..." (it invalidates any labelled test).'
        )
        return 1
    print(f"ok: version {frozen['version']} still matches (frozen {frozen['frozen_at_utc']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
