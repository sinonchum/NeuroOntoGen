"""OpenAI-compatible chat-completions provider primitives."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonMapping = Mapping[str, Any]
PostJson = Callable[[str, Mapping[str, str], Mapping[str, Any], float], JsonMapping]
Sleep = Callable[[float], None]

RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot be configured from the local environment."""


class ProviderResponseError(RuntimeError):
    """Raised when a provider response is missing the expected structured content."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        diagnostics = []
        if request_id:
            diagnostics.append(f"request_id={request_id}")
        if retry_after_seconds is not None:
            diagnostics.append(f"retry_after={retry_after_seconds:g}s")
        if diagnostics:
            message = f"{message} ({', '.join(diagnostics)})"
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.request_id = request_id
        self.retry_after_seconds = retry_after_seconds


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
        request_id = _extract_header_value(
            exc.headers,
            "x-request-id",
            "request-id",
            "x-correlation-id",
            "cf-ray",
        )
        retry_after_seconds = _parse_retry_after(_extract_header_value(exc.headers, "retry-after"))
        raise ProviderResponseError(
            f"provider HTTP error {exc.code}: {_redact_response_body(body)}",
            status_code=exc.code,
            retryable=exc.code in RETRYABLE_HTTP_STATUS_CODES,
            request_id=request_id,
            retry_after_seconds=retry_after_seconds,
        ) from exc
    except URLError as exc:
        raise ProviderResponseError(f"provider network error: {exc.reason}", retryable=True) from exc

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


def _extract_header_value(headers: Any, *names: str) -> str | None:
    """Return a response header value using case-insensitive matching."""
    if not headers:
        return None
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value:
            return value
    return None


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After seconds or HTTP-date header into seconds."""
    if not value:
        return None
    stripped = value.strip()
    try:
        seconds = float(stripped)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        seconds = retry_at.timestamp() - time.time()
    return max(0.0, seconds)


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    """Provider-neutral OpenAI-compatible chat-completions adapter."""

    api_key: str
    base_url: str
    model: str
    provider_name: str
    timeout: float = 60.0
    temperature: float = 0
    max_retries: int = 0
    retry_delay: float = 0.0
    system_prompt: str = (
        "You are NeuroOntoGen's ontology extraction provider. "
        "Return only JSON matching the requested schema."
    )
    post_json: PostJson = field(default=_default_post_json, repr=False, compare=False)
    sleep: Sleep = field(default=time.sleep, repr=False, compare=False)

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
        max_retries_env: str | None = None,
        retry_delay_env: str | None = None,
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
        max_retries = int(os.getenv(max_retries_env or "", str(cls.max_retries)))
        retry_delay = float(os.getenv(retry_delay_env or "", str(cls.retry_delay)))
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "provider_name": provider_name,
            "timeout": timeout,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
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
        response = self._post_json_with_retries(endpoint, headers, payload)
        return self._extract_message_content(response)

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
