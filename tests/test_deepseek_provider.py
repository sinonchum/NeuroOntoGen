from neuro_onto_gen.providers import DeepSeekProvider, ProviderConfigurationError


def test_deepseek_provider_posts_openai_compatible_chat_completion() -> None:
    calls = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {"choices": [{"message": {"content": '{"employees": [], "secure_assets": [], "relations": []}'}}]}

    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.example/v1",
        model="deepseek-v4-pro",
        timeout=12,
        post_json=fake_post_json,
    )

    content = provider.complete("Extract CompanyAccess facts.")

    assert content == '{"employees": [], "secure_assets": [], "relations": []}'
    assert len(calls) == 1
    url, headers, payload, timeout = calls[0]
    assert url == "https://api.deepseek.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert "Return only JSON" in payload["messages"][0]["content"]
    assert payload["messages"][1] == {"role": "user", "content": "Extract CompanyAccess facts."}
    assert timeout == 12


def test_deepseek_provider_from_env_reads_deepseek_variables(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://deepseek.local/v1/")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT", "9")

    provider = DeepSeekProvider.from_env()

    assert provider.api_key == "env-key"
    assert provider.base_url == "https://deepseek.local/v1"
    assert provider.model == "deepseek-v4-pro"
    assert provider.timeout == 9


def test_deepseek_provider_from_env_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    try:
        DeepSeekProvider.from_env()
    except ProviderConfigurationError as exc:
        assert "DEEPSEEK_API_KEY" in str(exc)
        assert "deepseek" in str(exc)
    else:
        raise AssertionError("DeepSeek provider should require DEEPSEEK_API_KEY")
