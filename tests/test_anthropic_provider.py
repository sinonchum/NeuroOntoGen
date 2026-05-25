from neuro_onto_gen.cli import build_completion_provider, build_extraction_adapter
from neuro_onto_gen.providers import AnthropicProvider, ProviderConfigurationError, ProviderResponseError


def test_anthropic_provider_posts_messages_completion() -> None:
    calls = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {"content": [{"type": "text", "text": '{"employees": [], "secure_assets": [], "relations": []}'}]}

    provider = AnthropicProvider(
        api_key="test-key",
        base_url="https://api.anthropic.example/v1",
        model="claude-3-5-haiku-latest",
        timeout=12,
        post_json=fake_post_json,
    )

    content = provider.complete("Extract CompanyAccess facts.")

    assert content == '{"employees": [], "secure_assets": [], "relations": []}'
    assert len(calls) == 1
    url, headers, payload, timeout = calls[0]
    assert url == "https://api.anthropic.example/v1/messages"
    assert headers["x-api-key"] == "test-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "claude-3-5-haiku-latest"
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 4096
    assert payload["system"].startswith("You are NeuroOntoGen")
    assert payload["messages"] == [{"role": "user", "content": "Extract CompanyAccess facts."}]
    assert timeout == 12


def test_anthropic_provider_from_env_reads_anthropic_variables(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic.local/v1/")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    monkeypatch.setenv("ANTHROPIC_TIMEOUT", "9")
    monkeypatch.setenv("ANTHROPIC_MAX_RETRIES", "2")
    monkeypatch.setenv("ANTHROPIC_RETRY_DELAY", "0.5")

    provider = AnthropicProvider.from_env()

    assert provider.api_key == "env-key"
    assert provider.base_url == "https://anthropic.local/v1"
    assert provider.model == "claude-3-5-sonnet-latest"
    assert provider.timeout == 9
    assert provider.max_retries == 2
    assert provider.retry_delay == 0.5


def test_anthropic_provider_from_env_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    try:
        AnthropicProvider.from_env()
    except ProviderConfigurationError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
        assert "anthropic" in str(exc)
    else:
        raise AssertionError("Anthropic provider should require ANTHROPIC_API_KEY")


def test_anthropic_provider_rejects_missing_text_content() -> None:
    provider = AnthropicProvider(
        api_key="test-key",
        post_json=lambda *_args: {"content": [{"type": "tool_use", "name": "noop"}]},
    )

    try:
        provider.complete("prompt")
    except ProviderResponseError as exc:
        assert "text content" in str(exc)
    else:
        raise AssertionError("Anthropic provider should require text content")


def test_anthropic_provider_can_be_built_for_completion_and_extraction(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic.local/v1")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

    completion_provider = build_completion_provider("anthropic")
    extraction_adapter = build_extraction_adapter("claude")

    assert isinstance(completion_provider, AnthropicProvider)
    assert completion_provider.provider_name == "anthropic"
    assert extraction_adapter.provider.provider_name == "anthropic"
