"""The OSS pack's definition (docs/HEARTHGUARD.md §4.2). A pack provides exactly four things:

  (1) source parsers      packs/oss/git_ingest.py, mail_cache.py, github_cache.py (not here)
  (2) a mapping from its records to core concepts: PRIVILEGES, ACTION_KINDS, PLACE_KINDS below
  (3) its claim vocabulary for the Reader: CLAIM_VOCABULARY
  (4) its "normal path" definition: NORMAL_PATH

Core imports nothing from packs/ (tests/unit/test_pack_oss.py scans for it). This module may import
from core. The finance pack, when it exists, is another file of the same shape.

Choices that are the pack's, not the spec's (change them here, never in core):
  - `merge` is not sensitive on its own: a merge is reviewed before it ships. `release`, `sign`
    and `npm_publish` are, because each one is the power to ship (§2.2).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PrivilegeKind:
    kind: str
    sensitive: bool
    meaning: str


# §6.1: OSS privileges are merge | release | sign | npm_publish.
PRIVILEGES: tuple[PrivilegeKind, ...] = (
    PrivilegeKind("merge", False, "push or merge to the main branch"),
    PrivilegeKind("release", True, "tag and publish a release"),
    PrivilegeKind("sign", True, "sign release artifacts or tags"),
    PrivilegeKind("npm_publish", True, "publish a package version to npm"),
)
PRIVILEGE_KINDS: tuple[str, ...] = tuple(p.kind for p in PRIVILEGES)
SENSITIVE_PRIVILEGES: tuple[str, ...] = tuple(p.kind for p in PRIVILEGES if p.sensitive)

# §6.1 OSS mapping: commits, PRs, issues, reviews, emails, bug reports -> Action.
ACTION_KINDS: tuple[str, ...] = (
    "commit",
    "review",
    "pr",
    "issue",
    "email",
    "bug_report",
    "release",
)

# §6.1: mailing list, repo, tracker (and CI) -> Place.
PLACE_KINDS: tuple[str, ...] = ("list", "repo", "tracker", "ci")

# §7.1 Bypass, OSS: CI -> none, provenance -> none, new key, publisher outside the set, release
# artifact differs from tagged source. The Path property that carries each one:
NORMAL_PATH_PROPERTIES: tuple[str, ...] = (
    "channel",
    "verified",
    "ci",
    "provenance",
    "key_hid",
    "publisher_in_set",
    "artifact_matches_tag",
)
NORMAL_PATH = {
    "description": "CI + provenance + known publishers (§4.2)",
    "properties": NORMAL_PATH_PROPERTIES,
    "remembered_as": "the most common value of each property among earlier releases (§6.1 Normal)",
    "applies_to_action_kind": "release",
}

# §6.1 Claim kinds, with the Reader's meaning for each in an open-source project.
CLAIM_VOCABULARY: dict[str, str] = {
    "PRESSURE": "pushes the maintainer to act faster or differently, or complains they are slow",
    "URGENCY": "stresses time pressure or a deadline",
    "VOUCH": "endorses a person as trustworthy or competent, or recommends them for a role",
    "REQUESTS_PRIVILEGE": "asks to be given rights over the project (commit, release, maintainer)",
    "CAPACITY_STATEMENT": "says someone's time, resources or ability to maintain is limited",
    "CHANGE_REQUEST": "asks that who maintains or controls the project change",
    "HANDOVER_ANNOUNCEMENT": "announces that responsibility or access has been, or is being, "
    "handed over",
}
