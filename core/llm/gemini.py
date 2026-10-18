"""Gemini LLM client: OpenAI-compatible, cached, spend-capped.

This client interfaces with Google's Gemini models via the OpenAI-compatible REST endpoint:
https://generativelanguage.googleapis.com/v1beta/openai/chat/completions

Key handling:
  - Read from GEMINI_API_KEY in .env (or environment).
  - Sent via Authorization: Bearer <key> header.
  - Never printed, logged, stored in cache, or included in error messages.

Spend tracking:
  - Tracks estimated cost in INR (input and output tokens * model price * USD_TO_INR).
  - Stops automatically with SpendLimitReached when cumulative spend reaches the configured
    limit (default ₹150.00).
  - Price source: https://ai.google.dev/pricing
"""

import hashlib
import json
import math
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from core.llm.client import (
    CHARS_PER_TOKEN,
    MAX_RETRIES,
    MAX_VALIDATION_RETRIES,
    RATE_HEADERS,
    REPO_ROOT,
    CallRecord,
    DailyLimitReached,
    InvalidJSON,
    LLMError,
    LLMHTTPError,
    RateLimiter,
    Result,
    _canonical,
    cache_key,
    load_config,
    prompt_hash,
    strict_schema,
)

KEY_ENV = "GEMINI_API_KEY"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

# Pricing source: https://ai.google.dev/pricing (Google AI Developer Pricing)
PRICING_SOURCE = "https://ai.google.dev/pricing (Google AI Studio Developer API Pricing)"
USD_TO_INR = 84.00
DEFAULT_MAX_SPEND_INR = 150.0

# Pricing per 1M tokens in USD: (input_price_per_1M, output_price_per_1M)
# From https://ai.google.dev/pricing
GEMINI_PRICING_PER_1M_USD: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-flash-latest": (0.075, 0.30),
    "gemini-1.5-flash-8b": (0.0375, 0.15),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-exp": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash-lite-preview-02-05": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-pro-latest": (1.25, 5.00),
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.8-flash-lite": (0.075, 0.30),
    "gemini-flash-latest": (0.10, 0.40),
}


class SpendLimitReached(LLMError):
    """The cumulative spend on Gemini calls has reached the configured INR limit."""


def api_key() -> str | None:
    load_dotenv()
    return os.environ.get(KEY_ENV, "").strip() or None


def estimate_call_cost_inr(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    usd_to_inr: float = USD_TO_INR,
) -> float:
    """Calculate the estimated call cost in INR using official pricing from https://ai.google.dev/pricing."""
    pricing = None
    for k, v in GEMINI_PRICING_PER_1M_USD.items():
        if model == k or model.startswith(k):
            pricing = v
            break
    if pricing is None:
        # Default to standard gemini-2.0-flash pricing if unlisted
        pricing = (0.10, 0.40)
    in_price_per_m, out_price_per_m = pricing
    cost_usd = (input_tokens / 1_000_000.0) * in_price_per_m + (
        output_tokens / 1_000_000.0
    ) * out_price_per_m
    return cost_usd * usd_to_inr


class _FromEnvironment:
    """Marks 'read key from GEMINI_API_KEY'."""


FROM_ENVIRONMENT = _FromEnvironment()


class GeminiClient:
    """Gemini API client matching the LLMClient interface, with spend tracking and spend stop."""

    def __init__(
        self,
        config: dict | None = None,
        *,
        key: str | None | _FromEnvironment = FROM_ENVIRONMENT,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
        timeout_s: float = 120.0,
        max_spend_inr: float = DEFAULT_MAX_SPEND_INR,
    ) -> None:
        self.config = config if config is not None else {}
        self._key = api_key() if isinstance(key, _FromEnvironment) else key
        self.base_url = (base_url or self.config.get("gemini_base_url") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        cache = Path(
            cache_dir
            or self.config.get("cache_dir")
            or REPO_ROOT / "data" / "llm_cache"
        )
        self.cache_dir = cache if cache.is_absolute() else REPO_ROOT / cache
        self._clock, self._sleep, self._log = clock, sleep, log
        self.max_spend_inr = max_spend_inr
        self.cumulative_spend_inr = self._load_spend()
        self.limiter = RateLimiter(
            self.config.get(
                "rate_limit",
                {"tokens_per_minute": 1_000_000, "requests_per_minute": 60, "requests_per_day": 10_000},
            ),
            usage_path=self.cache_dir / "gemini_usage.json",
            clock=clock,
            sleep=sleep,
            log=log,
        )
        self._http = httpx.Client(timeout=timeout_s)
        self.calls: list[CallRecord] = []

    @property
    def has_key(self) -> bool:
        return self._key is not None

    # -- persistent spend tracking
    def _spend_file(self) -> Path:
        return self.cache_dir / "gemini_spend.json"

    def _load_spend(self) -> float:
        path = self._spend_file()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return float(data.get("cumulative_spend_inr", 0.0))
            except (ValueError, KeyError):
                return 0.0
        return 0.0

    def _save_spend(self) -> None:
        path = self._spend_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cumulative_spend_inr": self.cumulative_spend_inr,
            "max_spend_inr": self.max_spend_inr,
            "pricing_source": PRICING_SOURCE,
            "usd_to_inr": USD_TO_INR,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

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
            return None

    def _write_cache(
        self, key: str, model: str, prompt: str, schema: dict, text: str, rec: dict
    ) -> None:
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

    # -- complete_json
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
                )
                self._record(rec)
                return Result(cached, rec)

        if not self._key:
            raise LLMError(f"{KEY_ENV} is not set; add it to .env (git-ignored)")

        # Check spend stop before initiating an API call
        if self.cumulative_spend_inr >= self.max_spend_inr:
            raise SpendLimitReached(
                f"spend limit of INR {self.max_spend_inr:.2f} reached "
                f"(spent INR {self.cumulative_spend_inr:.4f}); pricing source: {PRICING_SOURCE}"
            )

        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
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
            raw_text = reply["choices"][0]["message"].get("content") or ""
            # Strip markdown code blocks if the model wrapped the JSON
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned_text)
                cleaned_text = re.sub(r"\n?```$", "", cleaned_text).strip()

            try:
                parsed = schema_model.model_validate_json(cleaned_text, strict=False)
            except (ValueError, ValidationError) as e:
                last_problem = self._validation_summary(e, reply)
                self._log(f"reply was not valid for the schema ({last_problem}); asking again")
                continue

            # Calculate and record estimated cost in INR
            call_cost_inr = estimate_call_cost_inr(model, totals["input"], totals["output"])
            self.cumulative_spend_inr += call_cost_inr
            self._save_spend()
            self._log(
                f"Gemini call [{model}]: {totals['input']} in, {totals['output']} out, "
                f"cost=INR {call_cost_inr:.4f} (cumulative=INR {self.cumulative_spend_inr:.4f} / {self.max_spend_inr:.2f})"
            )

            rec = CallRecord(
                model, prompt_hash(prompt), key, totals["input"], totals["output"],
                totals["reasoning"], (self._clock() - started) * 1000, False, status,
                attempts, True, headers,
            )
            self._record(rec)
            if use_cache:
                self._write_cache(key, model, prompt, schema, cleaned_text, rec.as_dict())
            return Result(parsed, rec)

        rec = CallRecord(
            model, prompt_hash(prompt), key, totals["input"], totals["output"],
            totals["reasoning"], (self._clock() - started) * 1000, False, status,
            attempts, False, headers,
        )
        self._record(rec)
        raise InvalidJSON(
            f"no valid JSON for the schema after {1 + MAX_VALIDATION_RETRIES} attempts "
            f"({last_problem})"
        )

    @staticmethod
    def _validation_summary(error: Exception, reply: dict) -> str:
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

    def _send(self, model: str, body: dict, est: int, totals: dict):
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        sent = 0
        server_retries = 0
        while True:
            resp = None
            slot = self.limiter.before(model, est)
            sent += 1
            try:
                resp = self._http.post(url, headers=headers, json=body)
            except httpx.TransportError as e:
                problem = f"network error ({type(e).__name__})"
                self.limiter.settle(model, slot, 0)
                server_retries += 1
                if server_retries > MAX_RETRIES:
                    raise LLMError(f"{problem} after {MAX_RETRIES} retries")
                wait = float(2**min(server_retries, 5))
                self._log(f"{problem}; retrying in {wait:.1f}s ({server_retries} of {MAX_RETRIES})")
                self._sleep(wait)
                continue
            else:
                if resp.status_code == 200:
                    reply = resp.json()
                    self._add_usage(totals, reply.get("usage") or {})
                    used = (reply.get("usage") or {}).get("total_tokens")
                    self.limiter.settle(model, slot, used)
                    seen = {h: resp.headers[h] for h in RATE_HEADERS if h in resp.headers}
                    return reply, 200, seen, sent

                self.limiter.settle(model, slot, 0)

                # Requirement: On 429 response, wait for retry-after and continue. Do not stop for rate limits.
                if resp.status_code == 429:
                    wait = self._backoff(sent, resp)
                    self._log(f"HTTP 429 (rate limit): waiting {wait:.1f}s and continuing...")
                    self._sleep(wait)
                    continue

                if resp.status_code < 500:
                    raise LLMHTTPError(resp.status_code, self._error_detail(resp))

                # 5xx server error
                problem = f"HTTP {resp.status_code}"
                server_retries += 1
                if server_retries > MAX_RETRIES:
                    raise LLMError(f"{problem} after {MAX_RETRIES} retries")
                wait = self._backoff(server_retries, resp)
                self._log(f"{problem}; retrying in {wait:.1f}s ({server_retries} of {MAX_RETRIES})")
                self._sleep(wait)

    @staticmethod
    def _backoff(retry: int, resp: httpx.Response | None) -> float:
        after = resp.headers.get("retry-after") if resp is not None else None
        if after and re.fullmatch(r"\d+(\.\d+)?", after):
            return float(after) + 0.5
        if resp is not None:
            try:
                err_text = resp.text
                m = re.search(r"retry after ([0-9]+(?:\.[0-9]+)?)s", err_text, re.IGNORECASE)
                if m:
                    return float(m.group(1)) + 1.0
            except Exception:
                pass
        return float(2**min(retry, 5))

    @staticmethod
    def _add_usage(totals: dict, usage: dict) -> None:
        totals["input"] += usage.get("prompt_tokens") or 0
        totals["output"] += usage.get("completion_tokens") or 0
        details = usage.get("completion_tokens_details") or {}
        if details.get("reasoning_tokens") is not None:
            totals["reasoning"] = (totals["reasoning"] or 0) + details["reasoning_tokens"]

    def _error_detail(self, resp: httpx.Response) -> str:
        try:
            err = resp.json().get("error", {})
            if isinstance(err, list) and err:
                err = err[0].get("error", err[0])
            text = f"{err.get('status', err.get('type', 'error'))}: {err.get('message', '')}"
        except (ValueError, AttributeError):
            text = "no readable error body"
        if self._key:
            text = text.replace(self._key, "[key removed]")
        return text[:300]

    def list_model_ids(self) -> list[str]:
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
