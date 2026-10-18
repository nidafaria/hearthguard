from core.llm.client import (
    CallRecord,
    DailyLimitReached,
    InvalidJSON,
    LLMError,
    LLMHTTPError,
    LLMClient,
    Result,
    load_config,
    strict_schema,
)
from core.llm.gemini import (
    DEFAULT_MAX_SPEND_INR,
    PRICING_SOURCE,
    USD_TO_INR,
    GeminiClient,
    SpendLimitReached,
    estimate_call_cost_inr,
)


def get_client_for_model(model: str | None = None, **kwargs) -> LLMClient | GeminiClient:
    """Return an LLM client suited for the specified model name."""
    if model and model.startswith("gemini"):
        return GeminiClient(**kwargs)
    return LLMClient(**kwargs)
