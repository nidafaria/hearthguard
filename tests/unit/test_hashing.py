"""Identifier hashing: same input and salt give the same hash; a different salt changes it."""

import pytest

from core.graph.hashing import SALT_ENV, MissingSaltError, identifier_hash


def test_same_input_and_salt_give_same_hash():
    a = identifier_hash("octocat", salt=b"salt-one")
    b = identifier_hash("octocat", salt=b"salt-one")
    assert a == b
    assert len(a) == 64  # hex SHA-256


def test_different_salts_give_different_hashes():
    a = identifier_hash("octocat", salt=b"salt-one")
    b = identifier_hash("octocat", salt=b"salt-two")
    assert a != b


def test_different_inputs_give_different_hashes():
    assert identifier_hash("alice", salt=b"s") != identifier_hash("bob", salt=b"s")


def test_hash_is_not_plain_sha256():
    # The salt must actually be used: an unsalted digest of the same value must differ.
    import hashlib

    unsalted = hashlib.sha256(b"octocat").hexdigest()
    assert identifier_hash("octocat", salt=b"s") != unsalted


def test_salt_comes_from_environment(monkeypatch):
    monkeypatch.setenv(SALT_ENV, "env-salt")
    assert identifier_hash("octocat") == identifier_hash("octocat", salt=b"env-salt")


def test_missing_salt_is_refused(monkeypatch):
    # An empty value still counts as set, so load_dotenv() cannot refill it from .env.
    monkeypatch.setenv(SALT_ENV, "")
    with pytest.raises(MissingSaltError):
        identifier_hash("octocat")


def test_empty_explicit_salt_is_refused():
    with pytest.raises(MissingSaltError):
        identifier_hash("octocat", salt=b"")
