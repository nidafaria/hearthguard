"""Salted HMAC-SHA256 for identifiers (docs/HEARTHGUARD.md §1 R6, §6.1 `hid`).

The salt comes from HEARTHGUARD_HASH_SALT, read from the environment or a git-ignored .env.
It is never committed and has no default. Without it, hashing refuses to run.
Callers pass the canonical identifier. This module does not normalise it.
"""

import hashlib
import hmac
import os

from dotenv import load_dotenv

SALT_ENV = "HEARTHGUARD_HASH_SALT"


class MissingSaltError(RuntimeError):
    """The hashing salt is not configured."""


def load_salt() -> bytes:
    load_dotenv()  # never overrides a variable that is already set
    salt = os.environ.get(SALT_ENV, "")
    if not salt:
        raise MissingSaltError(f"{SALT_ENV} is not set; add it to .env (git-ignored)")
    return salt.encode("utf-8")


def identifier_hash(value: str, *, salt: bytes | None = None) -> str:
    """HMAC-SHA256 of `value`, hex encoded. Pass `salt` explicitly, or it is read from the env."""
    key = salt if salt is not None else load_salt()
    if not key:
        raise MissingSaltError("salt must not be empty")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
