"""The LLM response cache. A unit test of the cache logic, not of Groq.

The one test that needs a server uses a local HTTP stub: it counts requests so we can prove a
cache hit sends none.
"""

import json

from core.llm.client import cache_key, strict_schema
from tests.unit.llm_stub import CHAT, FAKE_KEY, Ok, Other, completion, make_client

MODEL = "openai/gpt-oss-20b"
PROMPT = 'Return JSON with one field "ok" set to true.'


def test_the_same_input_gives_the_same_key():
    schema = strict_schema(Ok)
    a = cache_key(MODEL, PROMPT, schema)
    assert a == cache_key(MODEL, PROMPT, strict_schema(Ok))
    assert len(a) == 64 and int(a, 16) >= 0  # SHA-256 in hex


def test_key_does_not_depend_on_the_order_of_keys_in_the_schema():
    one = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
    two = {"properties": {"b": {"type": "integer"}, "a": {"type": "string"}}, "type": "object"}
    assert cache_key(MODEL, PROMPT, one) == cache_key(MODEL, PROMPT, two)


def test_a_different_schema_gives_a_different_key():
    assert cache_key(MODEL, PROMPT, strict_schema(Ok)) != cache_key(
        MODEL, PROMPT, strict_schema(Other)
    )


def test_a_different_model_or_prompt_or_system_gives_a_different_key():
    schema = strict_schema(Ok)
    base = cache_key(MODEL, PROMPT, schema)
    assert base != cache_key("openai/gpt-oss-120b", PROMPT, schema)
    assert base != cache_key(MODEL, PROMPT + " ", schema)
    assert base != cache_key(MODEL, PROMPT, schema, system="Be brief.")
    assert cache_key(MODEL, PROMPT, schema, system=None) == base


def test_a_cache_hit_makes_no_network_call(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true}')
    client = make_client(site, tmp_path)
    first = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert first.data.ok is True and first.record.cache_hit is False
    assert len(site.posts) == 1

    second = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert second.data.ok is True and second.record.cache_hit is True
    assert len(site.posts) == 1  # no second request
    assert second.record.http_status is None and second.record.attempts == 0
    assert (second.record.input_tokens, second.record.output_tokens) == (0, 0)


def test_a_new_client_on_the_same_folder_also_hits_the_cache(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true}')
    make_client(site, tmp_path).complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    again = make_client(site, tmp_path).complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert again.record.cache_hit and len(site.posts) == 1


def test_a_cache_hit_works_without_a_key(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true}')
    make_client(site, tmp_path).complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    no_key = make_client(site, tmp_path, key=None)
    assert no_key.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok).record.cache_hit


def test_different_schemas_do_not_share_an_entry(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true, "note": "x"}')
    client = make_client(site, tmp_path)
    client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Other)
    assert len(site.posts) == 2


def test_the_cache_file_holds_the_reply_but_not_the_prompt_or_the_key(site, tmp_path):
    secret_prompt = "UNIQUE-PROMPT-TEXT-48151623 about a private-looking thing"
    site.routes[CHAT] = completion('{"ok": true}')
    client = make_client(site, tmp_path)
    client.complete_json(model=MODEL, prompt=secret_prompt, schema_model=Ok)
    files = [p for p in (tmp_path / "cache").iterdir() if p.is_file()]
    assert files
    text = "".join(p.read_text(encoding="utf-8") for p in files)
    assert "UNIQUE-PROMPT-TEXT-48151623" not in text
    assert FAKE_KEY not in text
    entry = json.loads(next(p for p in files if len(p.stem) == 64).read_text(encoding="utf-8"))
    assert entry["response_text"] == '{"ok": true}' and len(entry["prompt_sha256"]) == 64


def test_with_the_cache_off_every_call_goes_out(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true}')
    client = make_client(site, tmp_path)
    for _ in range(2):
        client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok, use_cache=False)
    assert len(site.posts) == 2
    assert not [p for p in (tmp_path / "cache").glob("*.json") if len(p.stem) == 64]  # none stored


def test_a_damaged_cache_entry_is_a_miss_not_a_crash(site, tmp_path):
    site.routes[CHAT] = completion('{"ok": true}')
    client = make_client(site, tmp_path)
    client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    entry = next(p for p in (tmp_path / "cache").glob("*.json") if len(p.stem) == 64)
    entry.write_text("{ not json", encoding="utf-8")
    again = client.complete_json(model=MODEL, prompt=PROMPT, schema_model=Ok)
    assert again.record.cache_hit is False and len(site.posts) == 2
