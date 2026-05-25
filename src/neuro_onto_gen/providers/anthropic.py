"""Anthropic Messages API provider adapter."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from neuro_onto_gen.providers.openai_compatible import (
    JsonMapping,
    PostJson,
    ProviderConfigurationError,
    ProviderResponseError,
    _default_post_json,
)


@dataclass(frozen=True)
class AnthropicProvider:
    """Provider-neutral completion adapter for Anthropic's Messages API."""

    api_key: str
    base_url: str = "https://api.anthropic.com/v1"
    model: str = "claude-3-5-haiku-latest"
    provider_name: str = "anthropic"
    timeout: float = 60.0
    temperature: float = 0
    max_tokens: int = 4096
    max_retries: int = 0
    retry_delay: float = 0.0
    anthropic_version: str = "2023-06-01"
    system_prompt: str = (
        "You are NeuroOntoGen's ontology extraction provider. "
        "Return only JSON matching the requested schema."
    )
    post_json: PostJson = field(default=_default_post_json, repr=False, compare=False)
    sleep: Any = field(default=time.sleep, repr=False, compare=False)

    @classmethod
    def from_env(cls) -> "AnthropicProvider":
        """Build a provider from ``ANTHROPIC_*`` environment variables."""
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError("ANTHROPIC_API_KEY is required for provider 'anthropic'")
        return cls(
            api_key=api_key,
            base_url=os.getenv("ANTHROPIC_BASE_URL", cls.base_url).strip().rstrip("/"),
            model=os.getenv("ANTHROPIC_MODEL", cls.model).strip() or cls.model,
            timeout=float(os.getenv("ANTHROPIC_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", str(cls.max_retries))),
            retry_delay=float(os.getenv("ANTHROPIC_RETRY_DELAY", str(cls.retry_delay))),
        )

    def complete(self, prompt: str) -> str:
        """Complete a rendered prompt and return assistant text content."""
        endpoint = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._post_json_with_retries(endpoint, headers, payload)
        return self._extract_text_content(response)

    def _post_json_with_retries(
        self,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> JsonMapping:
        attempts = max(0, self.max_retries) + 1
        for attempt_index in range(attempts):
            try:
                return self.post_json(endpoint, headers, payload, self.timeout)
            except ProviderResponseError as exc:
                is_last_attempt = attempt_index >= attempts - 1
                if is_last_attempt or not exc.retryable:
                    raise
                retry_delay = exc.retry_after_seconds
                if retry_delay is None:
                    retry_delay = self.retry_delay
                if retry_delay > 0:
                    self.sleep(retry_delay)
        raise RuntimeError("unreachable provider retry state")

    @staticmethod
    def _extract_text_content(response: JsonMapping) -> str:
        content = response.get("content")
        if not isinstance(content, list) or not content:
            raise ProviderResponseError("Anthropic response missing content[] text content")
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, Mapping) and item.get("type") == "text" and isinstance(item.get("text"), str)
        ]
        text = "".join(text_parts).strip()
        if not text:
            raise ProviderResponseError("Anthropic response missing content[] text content")
        return text
