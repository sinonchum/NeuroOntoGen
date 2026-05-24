"""OpenAI-compatible chat-completions provider primitives."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonMapping = Mapping[str, Any]
PostJson = Callable[[str, Mapping[str, str], Mapping[str, Any], float], JsonMapping]


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot be configured from the local environment."""


class ProviderResponseError(RuntimeError):
    """Raised when a provider response is missing the expected structured content."""


def _default_post_json(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> JsonMapping:
    """POST JSON using the Python standard library.

    The project keeps production provider integration optional and avoids adding
    mandatory HTTP SDK dependencies to the base install.
    """
    data = json.dumps(payload).encode("utf-8")
    request = Request(url=url, data=data, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-configured HTTPS API
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderResponseError(
            f"provider HTTP error {exc.code}: {_redact_response_body(body)}"
        ) from exc
    except URLError as exc:
        raise ProviderResponseError(f"provider network error: {exc.reason}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError("provider response was not valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise ProviderResponseError("provider response JSON must be an object")
    return parsed


def _redact_response_body(body: str) -> str:
    """Keep provider diagnostics useful without leaking accidental secrets."""
    redacted = body
    for env_name in ("XIAOMI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        secret = os.getenv(env_name, "").strip()
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted[:500]


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    """Provider-neutral OpenAI-compatible chat-completions adapter."""

    api_key: str
    base_url: str
    model: str
    provider_name: str
    timeout: float = 60.0
    temperature: float = 0
    system_prompt: str = (
        "You are NeuroOntoGen's ontology extraction provider. "
        "Return only JSON matching the requested schema."
    )
    post_json: PostJson = field(default=_default_post_json, repr=False, compare=False)

    @classmethod
    def from_env_vars(
        cls,
        *,
        provider_name: str,
        api_key_env: str,
        default_base_url: str,
        default_model: str,
        base_url_env: str | None = None,
        model_env: str | None = None,
        timeout_env: str | None = None,
        system_prompt: str | None = None,
    ) -> "OpenAICompatibleProvider":
        """Build a provider from a conventional set of environment variables."""
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                f"{api_key_env} is required for provider '{provider_name}'"
            )
        base_url = os.getenv(base_url_env or "", default_base_url).strip().rstrip("/")
        model = os.getenv(model_env or "", default_model).strip() or default_model
        timeout = float(os.getenv(timeout_env or "", str(cls.timeout)))
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "provider_name": provider_name,
            "timeout": timeout,
        }
        if system_prompt is not None:
            kwargs["system_prompt"] = system_prompt
        return cls(**kwargs)

    def complete(self, prompt: str) -> str:
        """Complete a rendered prompt and return assistant content."""
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.post_json(endpoint, headers, payload, self.timeout)
        return self._extract_message_content(response)

    @staticmethod
    def _extract_message_content(response: JsonMapping) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError("provider response missing choices[0]")
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise ProviderResponseError("provider response choices[0] must be an object")
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise ProviderResponseError("provider response missing choices[0].message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("provider response missing choices[0].message.content")
        return content
