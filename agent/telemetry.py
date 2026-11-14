"""Non-invasive LLMOps telemetry structures and provider usage extractors."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _safe_int(val: Any) -> int:
    """Extracts an integer token count safely, ignoring None, bools, and MagicMocks."""
    if isinstance(val, bool):
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(val))
    return 0


@dataclass
class TurnTelemetry:
    """Operational metrics recorded across a single agent consultation turn."""

    planner_ms: float = 0.0
    routing_ms: float = 0.0
    retrieval_ms: float = 0.0
    ttft_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0
    provider: str = ""
    model_used: str = ""
    fallback_triggered: bool = False
    fallback_reason: str = ""
    react_iterations: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def merge_usage(self, usage: dict[str, int] | None) -> None:
        if not isinstance(usage, dict):
            return
        p = _safe_int(usage.get("prompt_tokens"))
        c = _safe_int(usage.get("cached_tokens"))
        o = _safe_int(usage.get("completion_tokens"))
        t = _safe_int(usage.get("total_tokens"))
        self.prompt_tokens += p
        self.cached_tokens += c
        self.completion_tokens += o
        self.total_tokens += t if t > 0 else (p + o)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_gemini_usage(response: Any) -> dict[str, int]:
    """Safely extracts token and context-cache counts from a google-genai response or chunk."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    prompt_tokens = _safe_int(getattr(meta, "prompt_token_count", 0))
    cached_tokens = _safe_int(getattr(meta, "cached_content_token_count", 0))
    completion_tokens = _safe_int(getattr(meta, "candidates_token_count", 0))
    total_tokens = _safe_int(getattr(meta, "total_token_count", 0))
    if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def extract_openai_usage(response: Any) -> dict[str, int]:
    """Safely extracts token and cached-token counts from an OpenAI chat completion response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    prompt_tokens = _safe_int(getattr(usage, "prompt_tokens", 0))
    completion_tokens = _safe_int(getattr(usage, "completion_tokens", 0))
    total_tokens = _safe_int(getattr(usage, "total_tokens", 0))

    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = _safe_int(getattr(details, "cached_tokens", 0)) if details is not None else 0

    if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
