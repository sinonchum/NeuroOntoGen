import io

import pytest

from neuro_onto_gen.cli import build_completion_provider, build_extraction_adapter
from neuro_onto_gen.providers import OpenAICompatibleProvider, ProviderResponseError
from neuro_onto_gen.providers import openai_compatible as provider_module


def test_openai_compatible_provider_from_env_supports_custom_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "relay-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.shqbb.example/v1/")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_TIMEOUT", "7")

    provider = build_completion_provider("openai-compatible")

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_name == "openai-compatible"
    assert provider.api_key == "relay-key"
    assert provider.base_url == "https://api.shqbb.example/v1"
    assert provider.model == "gpt-4.1-mini"
    assert provider.timeout == 7


def test_openai_compatible_provider_can_be_used_for_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "relay-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.shqbb.example/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    adapter = build_extraction_adapter("openai-compatible")

    assert adapter.provider.provider_name == "openai-compatible"
    assert adapter.provider.base_url == "https://api.shqbb.example/v1"


def test_openai_compatible_provider_retries_retryable_provider_errors() -> None:
    calls = []

    def flaky_post_json(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        calls.append((url, headers, payload, timeout))
        if len(calls) < 3:
            raise ProviderResponseError(
                "provider HTTP error 429: rate limited",
                status_code=429,
                retryable=True,
            )
        return {"choices": [{"message": {"content": "{}"}}]}

    provider = OpenAICompatibleProvider(
        api_key="relay-key",
        base_url="https://api.shqbb.example/v1",
        model="gpt-4.1-mini",
        provider_name="openai-compatible",
        post_json=flaky_post_json,
        max_retries=2,
        retry_delay=0,
    )

    assert provider.complete("Return JSON") == "{}"
    assert len(calls) == 3


def test_openai_compatible_provider_does_not_retry_non_retryable_provider_errors() -> None:
    calls = []

    def failing_post_json(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("called")
        raise ProviderResponseError(
            "provider HTTP error 401: invalid_key",
            status_code=401,
            retryable=False,
        )

    provider = OpenAICompatibleProvider(
        api_key="relay-key",
        base_url="https://api.shqbb.example/v1",
        model="gpt-4.1-mini",
        provider_name="openai-compatible",
        post_json=failing_post_json,
        max_retries=3,
        retry_delay=0,
    )

    with pytest.raises(ProviderResponseError, match="401"):
        provider.complete("Return JSON")
    assert calls == ["called"]


def test_default_post_json_surfaces_http_request_id_and_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_http_error(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise provider_module.HTTPError(
            url="https://api.shqbb.example/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={"X-Request-ID": "req-relay-456", "Retry-After": "4"},
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        )

    monkeypatch.setattr(provider_module, "urlopen", raise_http_error)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider_module._default_post_json(
            "https://api.shqbb.example/v1/chat/completions",
            {"Authorization": "Bearer relay-key"},
            {"model": "gpt-4.1-mini"},
            1,
        )

    error = exc_info.value
    assert error.status_code == 429
    assert error.retryable is True
    assert error.request_id == "req-relay-456"
    assert error.retry_after_seconds == 4.0
    assert "request_id=req-relay-456" in str(error)
    assert "retry_after=4s" in str(error)


def test_openai_compatible_provider_error_preserves_request_id_and_retry_after() -> None:
    error = ProviderResponseError(
        "provider HTTP error 429: rate limited",
        status_code=429,
        retryable=True,
        request_id="req-relay-123",
        retry_after_seconds=2.5,
    )

    assert error.status_code == 429
    assert error.retryable is True
    assert error.request_id == "req-relay-123"
    assert error.retry_after_seconds == 2.5
    assert "request_id=req-relay-123" in str(error)
    assert "retry_after=2.5s" in str(error)


def test_openai_compatible_provider_prefers_retry_after_over_default_delay() -> None:
    sleep_calls: list[float] = []
    calls = []

    def rate_limited_then_success(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("called")
        if len(calls) == 1:
            raise ProviderResponseError(
                "provider HTTP error 429: rate limited",
                status_code=429,
                retryable=True,
                request_id="req-relay-123",
                retry_after_seconds=3.0,
            )
        return {"choices": [{"message": {"content": "{}"}}]}

    provider = OpenAICompatibleProvider(
        api_key="relay-key",
        base_url="https://api.shqbb.example/v1",
        model="gpt-4.1-mini",
        provider_name="openai-compatible",
        post_json=rate_limited_then_success,
        sleep=sleep_calls.append,
        max_retries=1,
        retry_delay=0.25,
    )

    assert provider.complete("Return JSON") == "{}"
    assert calls == ["called", "called"]
    assert sleep_calls == [3.0]
