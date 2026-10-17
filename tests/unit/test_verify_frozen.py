"""Row 77: verify-frozen compares docs/FREEZE.md to its recorded hash."""

import hashlib

from eval import verify_frozen as vf


def _pair(tmp_path, body: str, recorded: str | None = None):
    f = tmp_path / "FREEZE.md"
    f.write_bytes(body.encode())
    h = tmp_path / "FREEZE.sha256"
    h.write_text(f"{recorded or hashlib.sha256(body.encode()).hexdigest()} *docs/FREEZE.md\n")
    return f, h


def test_matching_hash_and_a_frozen_status(tmp_path):
    f, h = _pair(tmp_path, "# x\n\nStatus: FROZEN 2026-10-14.\n")
    r = vf.check(f, h)
    assert r["hash_matches"] is True and r["frozen"] is True


def test_matching_hash_on_a_draft_is_not_frozen(tmp_path):
    f, h = _pair(tmp_path, "# x\n\nStatus: DRAFT, local only.\n")
    r = vf.check(f, h)
    assert r["hash_matches"] is True and r["frozen"] is False


def test_an_edited_file_fails(tmp_path):
    f, h = _pair(tmp_path, "# x\n\nStatus: FROZEN.\n")
    f.write_bytes(b"# x\n\nStatus: FROZEN, edited.\n")
    r = vf.check(f, h)
    assert r["hash_matches"] is False and r["frozen"] is False


def test_the_repo_file_is_read_only_here():
    before = vf.FREEZE.read_bytes(), vf.HASH_FILE.read_bytes()
    vf.check()
    assert (vf.FREEZE.read_bytes(), vf.HASH_FILE.read_bytes()) == before
