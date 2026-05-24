"""DeepSeek OpenAI-compatible provider adapter."""

from __future__ import annotations

from dataclasses import dataclass

from neuro_onto_gen.providers.openai_compatible import OpenAICompatibleProvider, PostJson


@dataclass(frozen=True)
class DeepSeekProvider(OpenAICompatibleProvider):
    """OpenAI-compatible chat-completions adapter for DeepSeek."""

    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-v4-pro"
    provider_name: str = "deepseek"
    timeout: float = 60.0
    temperature: float = 0
    system_prompt: str = (
        "You are NeuroOntoGen's ontology extraction provider. "
        "Return only JSON matching the requested schema."
    )
    post_json: PostJson = OpenAICompatibleProvider.__dataclass_fields__["post_json"].default

    @classmethod
    def from_env(cls) -> "DeepSeekProvider":
        """Build a provider from ``DEEPSEEK_*`` environment variables."""
        provider = OpenAICompatibleProvider.from_env_vars(
            provider_name="deepseek",
            api_key_env="DEEPSEEK_API_KEY",
            base_url_env="DEEPSEEK_BASE_URL",
            model_env="DEEPSEEK_MODEL",
            timeout_env="DEEPSEEK_TIMEOUT",
            default_base_url=cls.base_url,
            default_model=cls.model,
        )
        return cls(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model,
            timeout=provider.timeout,
        )
