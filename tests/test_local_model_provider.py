from neuro_onto_gen.cli import build_completion_provider, build_extraction_adapter
from neuro_onto_gen.providers import LocalModelProvider


def test_local_model_provider_posts_openai_compatible_request_without_auth_by_default() -> None:
    calls = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {"choices": [{"message": {"content": '{"employees": [], "secure_assets": [], "relations": []}'}}]}

    provider = LocalModelProvider(
        base_url="http://localhost:11434/v1",
        model="llama3.1:8b",
        timeout=11,
        post_json=fake_post_json,
    )

    content = provider.complete("Extract CompanyAccess facts.")

    assert content == '{"employees": [], "secure_assets": [], "relations": []}'
    assert len(calls) == 1
    url, headers, payload, timeout = calls[0]
    assert url == "http://localhost:11434/v1/chat/completions"
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "llama3.1:8b"
    assert payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert "Return only JSON" in payload["messages"][0]["content"]
    assert payload["messages"][1] == {"role": "user", "content": "Extract CompanyAccess facts."}
    assert timeout == 11


def test_local_model_provider_adds_authorization_when_optional_key_is_set() -> None:
    calls = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {"choices": [{"message": {"content": "{}"}}]}

    provider = LocalModelProvider(
        api_key="local-secret",
        base_url="http://localhost:8000/v1",
        model="local-model",
        post_json=fake_post_json,
    )

    provider.complete("Return JSON")

    assert calls[0][1]["Authorization"] == "Bearer local-secret"


def test_local_model_provider_from_env_reads_local_model_variables_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:8000/v1/")
    monkeypatch.setenv("LOCAL_MODEL_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("LOCAL_MODEL_TIMEOUT", "8")
    monkeypatch.setenv("LOCAL_MODEL_MAX_RETRIES", "2")
    monkeypatch.setenv("LOCAL_MODEL_RETRY_DELAY", "0.25")

    provider = LocalModelProvider.from_env()

    assert provider.api_key == ""
    assert provider.base_url == "http://127.0.0.1:8000/v1"
    assert provider.model == "qwen2.5:7b"
    assert provider.timeout == 8
    assert provider.max_retries == 2
    assert provider.retry_delay == 0.25


def test_local_model_provider_can_be_built_for_completion_and_extraction(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCAL_MODEL_MODEL", "llama3.1:8b")

    completion_provider = build_completion_provider("local")
    extraction_adapter = build_extraction_adapter("ollama")

    assert isinstance(completion_provider, LocalModelProvider)
    assert completion_provider.provider_name == "local-model"
    assert extraction_adapter.provider.provider_name == "local-model"
