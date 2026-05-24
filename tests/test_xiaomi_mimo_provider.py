import json

import pytest

from neuro_onto_gen.providers import (
    ProviderConfigurationError,
    ProviderResponseError,
    XiaomiMiMoProvider,
)


def test_xiaomi_mimo_provider_posts_openai_compatible_chat_completion() -> None:
    calls = []

    def fake_post_json(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "employees": [{"emp_id": "E-001", "has_access_level": 3}],
                                "secure_assets": [
                                    {"asset_id": "VPN", "required_clearance": 2}
                                ],
                                "relations": [
                                    {
                                        "subject_emp_id": "E-001",
                                        "predicate": "operates",
                                        "object_asset_id": "VPN",
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    provider = XiaomiMiMoProvider(api_key="test-key", post_json=fake_post_json)

    raw_output = provider.complete("Return CompanyAccess JSON only.")

    assert json.loads(raw_output)["employees"][0]["emp_id"] == "E-001"
    assert len(calls) == 1
    url, headers, payload, timeout = calls[0]
    assert url == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "mimo-v2.5-pro"
    assert payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1] == {
        "role": "user",
        "content": "Return CompanyAccess JSON only.",
    }
    assert timeout == 60.0


def test_xiaomi_mimo_provider_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XIAOMI_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="XIAOMI_API_KEY"):
        XiaomiMiMoProvider.from_env()


def test_xiaomi_mimo_provider_from_env_uses_model_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XIAOMI_API_KEY", "env-key")
    monkeypatch.setenv("XIAOMI_BASE_URL", "https://example.invalid/custom/v1/")
    monkeypatch.setenv("XIAOMI_MODEL", "mimo-v2.5-pro")

    provider = XiaomiMiMoProvider.from_env()

    assert provider.api_key == "env-key"
    assert provider.base_url == "https://example.invalid/custom/v1"
    assert provider.model == "mimo-v2.5-pro"


def test_xiaomi_mimo_provider_rejects_missing_message_content() -> None:
    provider = XiaomiMiMoProvider(
        api_key="test-key",
        post_json=lambda *_args, **_kwargs: {"choices": [{"message": {}}]},
    )

    with pytest.raises(ProviderResponseError, match="message.content"):
        provider.complete("prompt")
