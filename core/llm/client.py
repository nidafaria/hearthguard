"""The one LLM client (docs/HEARTHGUARD.md §8.4): OpenAI-compatible, cached, rate-limited.

The LLM is used only to read text and to plan, never to decide (CLAUDE.md). This module only
makes a call and returns validated JSON; it knows nothing about claims, detectors or policy.

What a call does, in order:
  1. Cache: the key is SHA-256 of (model, system prompt if any, prompt, JSON schema). A hit returns
     the stored reply and makes no network call. The cache file holds the reply and token counts,
     never the prompt text and never the key.
  2. Rate limit: before each request the client sleeps until the request fits the per-minute
     limits, and it refuses (DailyLimitReached) rather than sleeping for hours when a daily limit
     is used up. The daily counters are saved to disk so they survive a restart.
  3. Request: strict JSON-schema output. The schema is made strict (every property required, no
     extra properties) as Groq's strict mode demands.
  4. Retries: 429, 5xx and network errors are retried with backoff, at most 3 retries. A 4xx
     other than 429 is not retried.
  5. Validation: the reply must parse and match the Pydantic model. If not, ask again, at most 2
     more times, then raise InvalidJSON.
  6. Record: model, prompt hash, input/output/reasoning tokens, latency, cache hit, status.

The API key is read from GROQ_API_KEY (environment or .env). It is sent as a header and is never
printed, logged, stored in the cache or put in an error message.
"""

import hashlib
import json
import math
import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "models.yaml"
KEY_ENV = "GROQ_API_KEY"

MAX_RETRIES = 3  # for 429, 5xx and network errors
MAX_VALIDATION_RETRIES = 2  # for a reply that is not valid JSON for the schema
CHARS_PER_TOKEN = 3  # only for pacing before a call; real counts are recorded from the reply
RATE_HEADERS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
)


class LLMError(RuntimeError):
    """Any failure of the LLM client."""


class DailyLimitReached(LLMError):
    """A daily request or token limit is used up. The client does not sleep until tomorrow."""


class LLMHTTPError(LLMError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class InvalidJSON(LLMError):
    """The reply was not valid JSON for the schema after every allowed retry."""


# ----------------------------------------------------------------------------- config
def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def api_key() -> str | None:
    load_dotenv()
    return os.environ.get(KEY_ENV, "").strip() or None


# ----------------------------------------------------------------------------- schema and cache key
def strict_schema(model: type[BaseModel]) -> dict:
    """The model's JSON schema, made strict: every property required, no extra properties."""
    schema = model.model_json_schema()
    _strictify(schema)
    return schema


def _strictify(node: Any) -> None:
    """Walk only the places a JSON schema can nest a sub-schema (not arbitrary dict values)."""
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        props = node.get("properties", {})
        node["additionalProperties"] = False
        node["required"] = list(props)
        for sub in props.values():
            _strictify(sub)
    if isinstance(node.get("items"), dict):
        _strictify(node["items"])
    for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for sub in node.get(keyword, []):
            _strictify(sub)
    for keyword in ("$defs", "definitions"):
        for sub in node.get(keyword, {}).values():
            _strictify(sub)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def cache_key(model: str, prompt: str, schema: dict, system: str | None = None) -> str:
    """SHA-256 of (model, prompt, schema). A system prompt, if any, is part of the prompt."""
    return hashlib.sha256(
        _canonical({"model": model, "system": system, "prompt": prompt, "schema": schema}).encode()
    ).hexdigest()


# ----------------------------------------------------------------------------- the rate limiter
class RateLimiter:
    """Per-model limits. Per-minute limits sleep. Daily limits raise.

    Daily counters are saved to `usage_path` (one entry per model, reset at 00:00 UTC) so a second
    process or a restart still sees what was used today.
    """

    def __init__(
        self,
        limits: dict,
        *,
        usage_path: Path | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
    ) -> None:
        self.tpm = limits.get("tokens_per_minute")
        self.rpm = limits.get("requests_per_minute")
        self.rpd = limits.get("requests_per_day")
        self.tpd = limits.get("tokens_per_day")
        self.usage_path = usage_path
        self._clock, self._sleep, self._log = clock, sleep, log
        self._window: dict[str, deque] = {}  # model -> deque of [timestamp, tokens]

    # -- daily counters, saved to disk
    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), UTC).strftime("%Y-%m-%d")

    def _load(self) -> dict:
        if self.usage_path and self.usage_path.is_file():
            return json.loads(self.usage_path.read_text(encoding="utf-8"))
        return {}

    def _daily(self, model: str) -> dict:
        entry = self._load().get(model, {})
        if entry.get("date") != self._today():
            return {"date": self._today(), "requests": 0, "tokens": 0}
        return entry

    def _save_daily(self, model: str, entry: dict) -> None:
        if not self.usage_path:
            return
        data = self._load()
        data[model] = entry
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.usage_path.with_name(self.usage_path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.usage_path)

    # -- the checks
    def before(self, model: str, est_tokens: int) -> list:
        """Wait until a request of about est_tokens fits. Returns the slot to settle later."""
        daily = self._daily(model)
        if self.rpd is not None and daily["requests"] >= self.rpd:
            raise DailyLimitReached(f"{model}: {self.rpd} requests per day used; resets 00:00 UTC")
        if self.tpd is not None and daily["tokens"] + est_tokens > self.tpd:
            raise DailyLimitReached(f"{model}: {self.tpd} tokens per day would be exceeded")
        if self.tpm is not None and est_tokens > self.tpm:
            raise LLMError(f"one request (about {est_tokens} tokens) exceeds {self.tpm} per minute")

        window = self._window.setdefault(model, deque())
        while True:
            now = self._clock()
            while window and window[0][0] <= now - 60:
                window.popleft()
            wait = self._wait_needed(window, est_tokens, now)
            if wait <= 0:
                break
            self._log(
                f"rate limit: waiting {wait:.1f}s so {model} stays within its per-minute limits"
            )
            self._sleep(wait)
        slot = [self._clock(), est_tokens]
        window.append(slot)
        daily["requests"] += 1
        daily["tokens"] += est_tokens
        self._save_daily(model, daily)
        return slot

    def _wait_needed(self, window: deque, est_tokens: int, now: float) -> float:
        waits = [0.0]
        if self.rpm is not None and len(window) >= self.rpm:
            waits.append(window[len(window) - self.rpm][0] + 60 - now)
        if self.tpm is not None:
            used = sum(tokens for _, tokens in window)
            if used + est_tokens > self.tpm:
                over, freed = used + est_tokens - self.tpm, 0
                for ts, tokens in window:
                    freed += tokens
                    if freed >= over:
                        waits.append(ts + 60 - now)
                        break
        return max(waits) + (0.01 if max(waits) > 0 else 0)

    def settle(self, model: str, slot: list, actual_tokens: int | None) -> None:
        """Replace the pacing estimate with the real token count once the reply is in."""
        if actual_tokens is None or slot is None:
            return
        daily = self._daily(model)
        daily["tokens"] += actual_tokens - slot[1]
        slot[1] = actual_tokens
        self._save_daily(model, daily)


# ----------------------------------------------------------------------------- records
@dataclass
class CallRecord:
    model: str
    prompt_sha256: str
    cache_key: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None  # None when the reply does not report them
    latency_ms: float
    cache_hit: bool
    http_status: int | None  # None on a cache hit
    attempts: int  # requests sent for this call, retries included
    json_valid: bool
    rate_headers: dict = field(
        default_factory=dict
    )  # the account's limits, if the reply shows them

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Result:
    data: BaseModel
    record: CallRecord


# ----------------------------------------------------------------------------- the client
class LLMClient:
    def __init__(
        self,
        config: dict | None = None,
        *,
        key: str | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
        timeout_s: float = 120.0,
    ) -> None:
        self.config = config if config is not None else load_config()
        self._key = key if key is not None else api_key()
        self.base_url = (base_url or self.config["base_url"]).rstrip("/")
        cache = Path(cache_dir or REPO_ROOT / self.config.get("cache_dir", "data/llm_cache"))
        self.cache_dir = cache if cache.is_absolute() else REPO_ROOT / cache
        self._clock, self._sleep, self._log = clock, sleep, log
        self.limiter = RateLimiter(
            self.config.get("rate_limit", {}),
            usage_path=self.cache_dir / "usage.json",
            clock=clock,
            sleep=sleep,
            log=log,
        )
        self._http = httpx.Client(timeout=timeout_s)
        self.calls: list[CallRecord] = []

    @property
    def has_key(self) -> bool:
        return self._key is not None

    # -- cache
    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str, schema_model: type[BaseModel]) -> BaseModel | None:
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            return schema_model.model_validate_json(entry["response_text"], strict=True)
        except (ValueError, KeyError, ValidationError):
            return None  # a damaged entry is a miss

    def _write_cache(self, key: str, model: str, prompt: str, schema: dict, text: str, rec: dict):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "cache_key": key,
            "model": model,
            "prompt_sha256": prompt_hash(prompt),
            "schema_sha256": hashlib.sha256(_canonical(schema).encode()).hexdigest(),
            "created_at_utc": datetime.fromtimestamp(self._clock(), UTC).isoformat(
                timespec="seconds"
            ),
            "response_text": text,
            "usage": {k: rec[k] for k in ("input_tokens", "output_tokens", "reasoning_tokens")},
        }
        path = self._cache_path(key)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    # -- the call
    def complete_json(
        self,
        *,
        model: str,
        prompt: str,
        schema_model: type[BaseModel],
        system: str | None = None,
        max_tokens: int = 1024,
        use_cache: bool = True,
    ) -> Result:
        schema = strict_schema(schema_model)
        key = cache_key(model, prompt, schema, system)
        started = self._clock()

        if use_cache:
            cached = self._read_cache(key, schema_model)
            if cached is not None:
                rec = CallRecord(
                    model, prompt_hash(prompt), key, 0, 0, None,
                    (self._clock() - started) * 1000, True, None, 0, True,
                )  # fmt: skip
                self._record(rec)
                return Result(cached, rec)

        if not self._key:
            raise LLMError(f"{KEY_ENV} is not set; add it to .env (git-ignored)")

        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_model.__name__, "strict": True, "schema": schema},
            },
        }
        est = math.ceil(len(_canonical(body)) / CHARS_PER_TOKEN) + max_tokens

        totals = {"input": 0, "output": 0, "reasoning": None}
        attempts, status, headers, last_problem = 0, None, {}, ""
        for _ in range(1 + MAX_VALIDATION_RETRIES):
            reply, status, headers, n = self._send(model, body, est, totals)
            attempts += n
            text = reply["choices"][0]["message"].get("content") or ""
            try:
                parsed = schema_model.model_validate_json(text, strict=True)
            except (ValueError, ValidationError) as e:
                last_problem = self._validation_summary(e, reply)
                self._log(f"reply was not valid for the schema ({last_problem}); asking again")
                continue
            rec = CallRecord(
                model, prompt_hash(prompt), key, totals["input"], totals["output"],
                totals["reasoning"], (self._clock() - started) * 1000, False, status,
                attempts, True, headers,
            )  # fmt: skip
            self._record(rec)
            if use_cache:
                self._write_cache(key, model, prompt, schema, text, rec.as_dict())
            return Result(parsed, rec)

        rec = CallRecord(
            model, prompt_hash(prompt), key, totals["input"], totals["output"],
            totals["reasoning"], (self._clock() - started) * 1000, False, status,
            attempts, False, headers,
        )  # fmt: skip
        self._record(rec)
        raise InvalidJSON(
            f"no valid JSON for the schema after {1 + MAX_VALIDATION_RETRIES} attempts "
            f"({last_problem})"
        )

    @staticmethod
    def _validation_summary(error: Exception, reply: dict) -> str:
        """Why a reply was rejected, without quoting the reply or the prompt."""
        finish = reply["choices"][0].get("finish_reason")
        if isinstance(error, ValidationError):
            errors = error.errors()
            if not any(e["type"] == "json_invalid" for e in errors):
                where = ", ".join(
                    sorted({".".join(map(str, e["loc"])) or "(root)" for e in errors})
                )
                return f"does not match the schema at: {where}"
        return f"not parseable as JSON (finish_reason={finish})"

    def _record(self, rec: CallRecord) -> None:
        self.calls.append(rec)
        log = self.cache_dir / "calls.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec.as_dict()) + "\n")

    # -- one request, with retries
    def _send(self, model: str, body: dict, est: int, totals: dict):
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        sent = 0
        for retry in range(MAX_RETRIES + 1):
            resp = None
            slot = self.limiter.before(model, est)
            sent += 1
            try:
                resp = self._http.post(url, headers=headers, json=body)
            except httpx.TransportError as e:
                problem = f"network error ({type(e).__name__})"
                self.limiter.settle(model, slot, 0)
            else:
                if resp.status_code == 200:
                    reply = resp.json()
                    self._add_usage(totals, reply.get("usage") or {})
                    used = (reply.get("usage") or {}).get("total_tokens")
                    self.limiter.settle(model, slot, used)
                    seen = {h: resp.headers[h] for h in RATE_HEADERS if h in resp.headers}
                    return reply, 200, seen, sent
                self.limiter.settle(model, slot, 0)
                if resp.status_code != 429 and resp.status_code < 500:
                    raise LLMHTTPError(resp.status_code, self._error_detail(resp))
                problem = f"HTTP {resp.status_code}"
            if retry == MAX_RETRIES:
                raise LLMError(f"{problem} after {MAX_RETRIES} retries")
            wait = self._backoff(retry, resp)
            self._log(f"{problem}; retrying in {wait:.1f}s ({retry + 1} of {MAX_RETRIES})")
            self._sleep(wait)
        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(retry: int, resp: httpx.Response | None) -> float:
        after = resp.headers.get("retry-after") if resp is not None else None
        if after and re.fullmatch(r"\d+(\.\d+)?", after):
            return float(after) + 0.5
        return float(2**retry)  # 1s, 2s, 4s

    @staticmethod
    def _add_usage(totals: dict, usage: dict) -> None:
        totals["input"] += usage.get("prompt_tokens") or 0
        totals["output"] += usage.get("completion_tokens") or 0
        details = usage.get("completion_tokens_details") or {}
        if details.get("reasoning_tokens") is not None:
            totals["reasoning"] = (totals["reasoning"] or 0) + details["reasoning_tokens"]

    def _error_detail(self, resp: httpx.Response) -> str:
        """The server's error type and message only, with the key removed. Never the request."""
        try:
            err = resp.json().get("error", {})
            text = f"{err.get('type', 'error')}: {err.get('message', '')}"
        except (ValueError, AttributeError):
            text = "no readable error body"
        if self._key:
            text = text.replace(self._key, "[key removed]")
        return text[:300]

    def list_model_ids(self) -> list[str]:
        """The model ids this account can use (GET /models). Costs no tokens."""
        if not self._key:
            raise LLMError(f"{KEY_ENV} is not set; add it to .env (git-ignored)")
        resp = self._http.get(
            f"{self.base_url}/models", headers={"Authorization": f"Bearer {self._key}"}
        )
        if resp.status_code != 200:
            raise LLMHTTPError(resp.status_code, self._error_detail(resp))
        return sorted(m["id"] for m in resp.json().get("data", []))

    def close(self) -> None:
        self._http.close()
