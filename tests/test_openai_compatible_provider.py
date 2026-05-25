import pytest

from neuro_onto_gen.cli import build_completion_provider, build_extraction_adapter
from neuro_onto_gen.providers import OpenAICompatibleProvider, ProviderResponseError


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
