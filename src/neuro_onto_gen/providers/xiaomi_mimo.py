"""Xiaomi MiMo OpenAI-compatible provider adapter."""

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
    return body.replace(os.getenv("XIAOMI_API_KEY", "<unset>"), "[REDACTED]")[:500]


@dataclass(frozen=True)
class XiaomiMiMoProvider:
    """OpenAI-compatible chat-completions adapter for Xiaomi MiMo.

    Defaults target the Xiaomi Token Plan China endpoint and the requested
    ``mimo-v2.5-pro`` model. The adapter returns the raw assistant message
    content so the existing NeuroOntoGen extraction boundary can validate it
    with Pydantic before any RDF/SHACL step.
    """

    api_key: str
    base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    model: str = "mimo-v2.5-pro"
    timeout: float = 60.0
    temperature: float = 0
    post_json: PostJson = field(default=_default_post_json, repr=False, compare=False)

    @classmethod
    def from_env(cls) -> "XiaomiMiMoProvider":
        """Build a provider from ``XIAOMI_*`` environment variables."""
        api_key = os.getenv("XIAOMI_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                "XIAOMI_API_KEY is required for provider 'xiaomi-mimo'"
            )
        base_url = os.getenv("XIAOMI_BASE_URL", cls.base_url).strip().rstrip("/")
        model = os.getenv("XIAOMI_MODEL", cls.model).strip() or cls.model
        timeout = float(os.getenv("XIAOMI_TIMEOUT", str(cls.timeout)))
        return cls(api_key=api_key, base_url=base_url, model=model, timeout=timeout)

    def complete(self, prompt: str) -> str:
        """Complete a rendered extraction prompt and return assistant content."""
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are NeuroOntoGen's ontology extraction provider. "
                        "Return only JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.post_json(endpoint, headers, payload, self.timeout)
        content = self._extract_message_content(response)
        return content

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
