"""Pure parsing helpers for the xz git ingest. No server, no network."""

from packs.oss.git_ingest import (
    PUBLIC_PERSONAS,
    classify_signature,
    hash_email,
    parse_shortstat,
)


def test_shortstat_counts_files():
    assert parse_shortstat("\n 3 files changed, 10 insertions(+), 2 deletions(-)\n") == 3
    assert parse_shortstat(" 1 file changed, 1 insertion(+)") == 1


def test_no_stat_line_means_zero_files():
    assert parse_shortstat("\n") == 0


def test_email_hash_is_case_and_space_insensitive_and_hides_the_email():
    a = hash_email("Someone@Example.org ")
    assert a == hash_email("someone@example.org")
    assert "@" not in a and "someone" not in a
    assert len(a) == 64


def test_signature_states():
    raw_nokey = "[GNUPG:] ERRSIG ABC 1 8 00 1 9 4\n[GNUPG:] NO_PUBKEY ABC\n"
    assert classify_signature(False, "") == "unsigned"
    assert classify_signature(True, raw_nokey) == "no_public_key"
    assert classify_signature(True, "[GNUPG:] GOODSIG ABC name\n[GNUPG:] VALIDSIG ABC\n") == "good"
    assert classify_signature(True, "[GNUPG:] BADSIG ABC name\n") == "bad"
    assert classify_signature(True, "[GNUPG:] EXPKEYSIG ABC name\n") == "key_expired_or_revoked"
    assert classify_signature(True, "gpg: something unexpected\n") == "error"


def test_only_the_public_persona_is_named():
    assert PUBLIC_PERSONAS == {"jia tan": "JiaT75"}
