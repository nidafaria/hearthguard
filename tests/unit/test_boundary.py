"""Action boundary (spec §4.4): each Never item is refused; a scan finds no outbound write."""

import ast
import sys
from pathlib import Path

import pytest

from core.policy import boundary as b

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".venv", "node_modules", "tests", "ui", "__pycache__", ".git"}


# Hand-worked: levels are 0 for analyse/draft/explain/simulate, 1 for the private note and its
# follow-up answers, 2 for a suggested step. Eight Never items, all refused.
def test_levels_are_as_the_spec_says():
    assert b.check("analyse") == b.Level.ANALYSE == 0
    assert b.check("simulate_hardening") == 0
    assert b.check("send_private_note", "owner") == b.Level.PRIVATE_NOTE == 1
    assert b.check("answer_followup", "backup") == 1
    assert b.check("suggest_safety_step", "owner") == b.Level.SUGGEST_STEP == 2


def test_never_list_has_exactly_the_eight_spec_items():
    assert set(b.NEVER) == {
        "post_publicly",
        "comment_on_issue_or_pr",
        "revoke_access",
        "block_release_or_payment",
        "contact_flagged_account",
        "label_attacker",
        "individual_risk_score",
        "publish_census_per_project",
    }


@pytest.mark.parametrize("action", sorted(b.NEVER))
@pytest.mark.parametrize("recipient", ["owner", "backup", "flagged", "public"])
def test_every_never_item_is_refused_for_every_recipient(action, recipient):
    with pytest.raises(b.BoundaryViolation) as e:
        b.check(action, recipient)
    assert e.value.rule == "never"


@pytest.mark.parametrize("recipient", ["flagged", "public", "channel", "", "stranger"])
@pytest.mark.parametrize("action", ["send_private_note", "answer_followup", "suggest_safety_step"])
def test_a_note_never_reaches_a_non_private_recipient(action, recipient):
    with pytest.raises(b.BoundaryViolation):
        b.check(action, recipient)


def test_the_flagged_account_is_named_in_the_refusal():
    with pytest.raises(b.BoundaryViolation) as e:
        b.check("send_private_note", "flagged")
    assert e.value.rule == "flagged"


@pytest.mark.parametrize("action", ["", "ban_user", "SEND_PRIVATE_NOTE", "post", "delete_repo"])
def test_an_unlisted_action_is_refused(action):
    with pytest.raises(b.BoundaryViolation) as e:
        b.check(action)
    assert e.value.rule == "unlisted"


def test_no_allowed_action_is_also_a_never_item():
    assert not set(b.ACTIONS) & set(b.NEVER)


# ---------------------------------------------------------------- static scan
WRITE_VERBS = {"post", "put", "patch", "delete", "send", "sendall", "sendmail", "send_message"}
SLACK_WRITES = {
    "chat_postMessage",
    "chat_postEphemeral",
    "chat_update",
    "views_open",
    "files_upload",
}
BANNED_IMPORTS = {"smtplib", "ftplib", "slack_sdk", "slack_bolt", "telnetlib"}
HTTP_WORDS = ("http", "session", "requests", "client", "slack", "web")


def _sources():
    for p in sorted(ROOT.rglob("*.py")):
        rel = p.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts):
            continue
        yield rel.as_posix(), ast.parse(p.read_text(encoding="utf-8"))


def _receiver(node: ast.expr) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts)).lower()


def _is_route_decorator(call: ast.Call, decorated: set[int]) -> bool:
    return id(call) in decorated


def outbound_writes() -> list[tuple[str, int, str]]:
    """(file, line, what) for each call that could write to the network."""
    found = []
    for rel, tree in _sources():
        decorators = {
            id(d)
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
            for d in n.decorator_list
        }
        for n in ast.walk(tree):
            if isinstance(n, ast.Import | ast.ImportFrom):
                names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                for name in names:
                    if name.split(".")[0] in BANNED_IMPORTS:
                        found.append((rel, n.lineno, f"import {name}"))
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            if _is_route_decorator(n, decorators):
                continue  # `@app.post(...)` declares an inbound route
            verb, recv = n.func.attr, _receiver(n.func.value)
            if verb in SLACK_WRITES or (verb in WRITE_VERBS and any(w in recv for w in HTTP_WORDS)):
                found.append((rel, n.lineno, f"{recv}.{verb}"))
    return found


def test_static_scan_finds_no_outbound_write_outside_the_allowed_modules():
    allowed = set(b.ALLOWED_NETWORK_WRITE_MODULES) | set(b.MODEL_ENDPOINT_MODULES)
    stray = [w for w in outbound_writes() if w[0] not in allowed]
    assert stray == []


def test_the_model_endpoint_is_the_only_outbound_write_today():
    # No sender is built. The one POST in the tree is the request for text to the model endpoint.
    files = {w[0] for w in outbound_writes()}
    assert files <= set(b.MODEL_ENDPOINT_MODULES)
    assert not any((ROOT / m).exists() for m in b.ALLOWED_NETWORK_WRITE_MODULES)


def test_the_scan_really_detects_an_outbound_write(tmp_path, monkeypatch):
    """Try to break the scan: a file with a Slack send must be reported."""
    bad = tmp_path / "evil.py"
    bad.write_text(
        "import requests\n"
        "requests.post('http://x', json={})\n"
        "client.chat_postMessage(channel='c')\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    found = outbound_writes()
    assert {w[2] for w in found} >= {"requests.post", "client.chat_postMessage"}
