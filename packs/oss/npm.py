"""npm registry parser (spec §4.2 source parsers, §6.1 OSS mapping): a packument -> releases.

Input is the JSON document `GET https://registry.npmjs.org/<package>` returns. Output is plain
dicts; nothing is written to a graph here (packs/oss/incidents_graph.py does that). Names are
hashed on the way in and never stored: a publisher or maintainer is `identifier_hash("npm:<name>")`.
The already-public, adjudicated attacker handle may be listed by the caller in `public_personas`.

What one version of a packument tells us, and what it does not:
  - `time[version]`       when the registry accepted it (UTC, ISO 8601)
  - `_npmUser`            who published it. Absent on some old versions: then the publisher is
                          None and the path property that needs it is left out, not guessed.
  - `_npmUser.trustedPublisher` set when the publish came from a CI workflow through npm's OIDC
                          trusted-publisher mechanism
  - `dist.attestations`   a provenance attestation; present or absent
  - `maintainers`         who could publish at that version
A version listed in `time` but missing from `versions` was unpublished or removed. It is returned in
`removed` with its time only: its publisher and path are NOT in the registry any more.

Path properties (the OSS list in core/detectors/bypass.py PACK_PROPERTIES), per release:
  channel            'npm_trusted_publisher' | 'npm_user'   (left out when `_npmUser` is absent)
  ci                 True if published by a CI workflow (trusted publisher), else False
  provenance         True if the version has an attestation
  publisher_in_set   True if the publisher published an earlier release of this package; left out
                     for the first release
`verified`, `key_hid` and `artifact_matches_tag` are not recorded by the registry and are left out.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from core.graph.hashing import identifier_hash

SKIP_TIME_KEYS = frozenset({"created", "modified"})


def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def npm_hid(name: str) -> str:
    return identifier_hash(f"npm:{name.strip().lower()}")


def parse_packument(
    doc: dict,
    hash_fn: Callable[[str], str] = npm_hid,
    public_personas: frozenset[str] = frozenset(),
) -> dict:
    package = doc["name"]
    times = doc.get("time", {})
    versions = doc.get("versions", {})
    personas: dict[str, str] = {}

    def hid_of(name: str) -> str:
        h = hash_fn(name)
        if name.lower() in public_personas:
            personas[h] = name
        return h

    releases = []
    for version, meta in versions.items():
        if version not in times:
            continue
        user = meta.get("_npmUser") or {}
        trusted = bool(user.get("trustedPublisher"))
        dist = meta.get("dist") or {}
        releases.append(
            {
                "ref": f"{package}@{version}",
                "package": package,
                "version": version,
                "at": epoch(times[version]),
                "publisher_hid": hid_of(user["name"]) if user.get("name") else None,
                "publisher_is_ci": trusted,
                "has_user": bool(user),
                "provenance": bool(dist.get("attestations")),
                "maintainer_hids": sorted(
                    {hid_of(m["name"]) for m in meta.get("maintainers", []) if m.get("name")}
                ),
            }
        )
    releases.sort(key=lambda r: (r["at"], r["version"]))

    seen_publishers: set[str] = set()
    for r in releases:
        path: dict = {}
        if r["has_user"]:
            path["channel"] = "npm_trusted_publisher" if r["publisher_is_ci"] else "npm_user"
            path["ci"] = r["publisher_is_ci"]
        path["provenance"] = r["provenance"]
        if r["publisher_hid"] and seen_publishers:
            path["publisher_in_set"] = r["publisher_hid"] in seen_publishers
        if r["publisher_hid"]:
            seen_publishers.add(r["publisher_hid"])
        r["path"] = path

    removed = sorted(
        (
            {"ref": f"{package}@{v}", "version": v, "at": epoch(t)}
            for v, t in times.items()
            if v not in SKIP_TIME_KEYS and v not in versions
        ),
        key=lambda r: (r["at"], r["version"]),
    )
    return {
        "package": package,
        "releases": releases,
        "removed": removed,
        "public_personas": personas,
        "maintainer_spans": maintainer_spans(releases),
    }


def maintainer_spans(releases: list[dict]) -> list[dict]:
    """First and last release time each maintainer is listed on. A removal is the end of a span,
    not a grant: the registry records no grant event, only the lists on published versions."""
    spans: dict[str, dict] = {}
    for r in releases:
        for h in r["maintainer_hids"]:
            s = spans.setdefault(
                h, {"hid": h, "first_listed_at": r["at"], "last_listed_at": r["at"]}
            )
            s["last_listed_at"] = r["at"]
    return sorted(spans.values(), key=lambda s: (s["first_listed_at"], s["hid"]))
