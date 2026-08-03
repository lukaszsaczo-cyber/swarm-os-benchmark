from __future__ import annotations

import os
import time
from typing import Any, Protocol

from .models import ProviderResponse, Usage


class Provider(Protocol):
    def generate(self, *, model: str, system: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float | None, metadata: dict[str, Any] | None = None) -> ProviderResponse: ...


class AnthropicProvider:
    def __init__(self, api_key: str | None = None, max_retries: int = 5) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install dependencies: pip install -r requirements.txt") from exc
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=key, max_retries=max_retries)

    def generate(self, *, model: str, system: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float | None, metadata: dict[str, Any] | None = None) -> ProviderResponse:
        started = time.perf_counter()
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        # Claude Sonnet 4.6 requires default sampling. Omitting temperature keeps
        # both benchmark conditions identical and avoids an API 400 response.
        if temperature is not None:
            request["temperature"] = temperature
        response = self._client.messages.create(**request)
        latency = (time.perf_counter() - started) * 1000
        text = "".join(getattr(block, "text", "") for block in response.content if getattr(block, "type", None) == "text")
        usage_obj = response.usage
        usage = Usage(
            input_tokens=int(getattr(usage_obj, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage_obj, "output_tokens", 0) or 0),
            cache_creation_input_tokens=int(getattr(usage_obj, "cache_creation_input_tokens", 0) or 0),
            cache_read_input_tokens=int(getattr(usage_obj, "cache_read_input_tokens", 0) or 0),
        )
        request_id = getattr(response, "_request_id", None) or getattr(response, "id", None)
        return ProviderResponse(
            text=text,
            usage=usage,
            model=str(getattr(response, "model", model)),
            stop_reason=getattr(response, "stop_reason", None),
            latency_ms=round(latency, 3),
            request_id=str(request_id) if request_id is not None else None,
        )
