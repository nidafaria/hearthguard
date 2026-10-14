"""npm packument and GitHub issue parsers (spec §4.2), on hand-written documents. No network.

Hand-worked expectations for the packument below (names are made up):
  1.0.0  alice, user publish, no attestation -> channel npm_user, ci False, provenance False,
         no publisher_in_set (first release)
  1.0.1  alice again                                  -> publisher_in_set True
  2.0.0  mallory, user publish, maintainers alice+mallory -> publisher_in_set False
  3.0.0  a CI workflow (trusted publisher) with an attestation -> channel
         npm_trusted_publisher, ci True, provenance True, publisher_in_set False
  2.0.1  in `time` but not in `versions` -> `removed`, with its time only
  A version without `_npmUser` has no channel and no publisher_in_set.
Names are hashed: no raw name appears anywhere in the output.
"""

import json

from packs.oss import npm, tracker

SALT = b"unit-test-salt-not-a-secret"


def h(value: str) -> str:
    from core.graph.hashing import identifier_hash

    return identifier_hash(value, salt=SALT)


def hash_fn(name: str) -> str:
    return h("npm:" + name.lower())


def doc():
    def v(user, maint, attest=False, trusted=False):
        u = {"name": user, "email": f"{user}@example.invalid"} if user else None
        if u and trusted:
            u["trustedPublisher"] = {"id": "github"}
        out = {"maintainers": [{"name": m} for m in maint], "dist": {}}
        if u:
            out["_npmUser"] = u
        if attest:
            out["dist"]["attestations"] = {"provenance": {}}
        return out

    return {
        "name": "pkg",
        "time": {
            "created": "2020-01-01T00:00:00.000Z",
            "modified": "2024-01-01T00:00:00.000Z",
            "0.9.0": "2020-01-01T00:00:00.000Z",
            "1.0.0": "2020-01-02T00:00:00.000Z",
            "1.0.1": "2020-02-01T00:00:00.000Z",
            "2.0.0": "2021-03-01T00:00:00.000Z",
            "2.0.1": "2021-03-02T00:00:00.000Z",
            "3.0.0": "2022-01-01T00:00:00.000Z",
        },
        "versions": {
            "0.9.0": v(None, ["alice"]),
            "1.0.0": v("alice", ["alice"]),
            "1.0.1": v("alice", ["alice"]),
            "2.0.0": v("mallory", ["alice", "mallory"]),
            "3.0.0": v("GitHub Actions", ["alice", "mallory"], attest=True, trusted=True),
        },
    }


def parsed():
    return npm.parse_packument(doc(), hash_fn, frozenset({"mallory"}))


def test_releases_are_in_time_order_with_paths():
    p = parsed()
    assert [r["version"] for r in p["releases"]] == ["0.9.0", "1.0.0", "1.0.1", "2.0.0", "3.0.0"]
    by = {r["version"]: r["path"] for r in p["releases"]}
    assert by["0.9.0"] == {"provenance": False}  # no _npmUser: no channel, nothing guessed
    assert by["1.0.0"] == {"channel": "npm_user", "ci": False, "provenance": False}
    assert by["1.0.1"]["publisher_in_set"] is True
    assert by["2.0.0"]["publisher_in_set"] is False
    assert by["3.0.0"] == {
        "channel": "npm_trusted_publisher",
        "ci": True,
        "provenance": True,
        "publisher_in_set": False,
    }


def test_removed_versions_carry_a_time_only():
    p = parsed()
    assert [(r["ref"], r["at"]) for r in p["removed"]] == [
        ("pkg@2.0.1", npm.epoch("2021-03-02T00:00:00Z"))
    ]


def test_maintainer_spans_and_public_persona():
    p = parsed()
    spans = {s["hid"]: s for s in p["maintainer_spans"]}
    assert spans[hash_fn("alice")]["first_listed_at"] == npm.epoch("2020-01-01T00:00:00Z")
    assert spans[hash_fn("mallory")]["first_listed_at"] == npm.epoch("2021-03-01T00:00:00Z")
    assert p["public_personas"] == {hash_fn("mallory"): "mallory"}


def test_no_raw_name_or_email_in_output():
    text = json.dumps(parsed())
    assert "alice" not in text.replace("mallory", "")  # persona handle may appear, alice may not
    assert "example.invalid" not in text


def test_issue_thread_events():
    issue = {
        "number": 7,
        "state": "closed",
        "created_at": "2018-11-20T10:00:00Z",
        "user": {"login": "Reporter"},
        "html_url": "https://github.com/o/r/issues/7",
    }
    comments = [
        {
            "id": 2,
            "created_at": "2018-11-20T12:00:00Z",
            "user": {"login": "maintainer"},
            "body": "text",
        },
        {
            "id": 1,
            "created_at": "2018-11-20T11:00:00Z",
            "user": {"login": "reporter"},
            "body": "text",
        },
        {"id": 3, "created_at": "2018-11-20T13:00:00Z", "user": None},
    ]
    t = tracker.parse_thread(
        issue,
        comments,
        "o/r",
        lambda login: h("github:" + login.lower()),
        frozenset({"maintainer"}),
    )
    assert [e["ref"] for e in t["events"]] == [
        "o/r#7",
        "o/r#7/comment/1",
        "o/r#7/comment/2",
        "o/r#7/comment/3",
    ]
    assert t["events"][0]["actor_hid"] == t["events"][1]["actor_hid"]  # same login, any case
    assert t["events"][3]["actor_hid"] is None
    assert list(t["public_personas"].values()) == ["maintainer"]
    assert "text" not in json.dumps(t)  # comment text is never returned
