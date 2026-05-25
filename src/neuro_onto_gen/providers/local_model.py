"""Local OpenAI-compatible model provider adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from neuro_onto_gen.providers.openai_compatible import OpenAICompatibleProvider, PostJson


@dataclass(frozen=True)
class LocalModelProvider(OpenAICompatibleProvider):
    """OpenAI-compatible adapter for local/private model servers.

    Targets local servers that implement ``/v1/chat/completions`` such as
    Ollama's OpenAI-compatible endpoint, vLLM, llama.cpp server, LM Studio, or
    a private relay. Unlike hosted providers, authentication is optional.
    """

    api_key: str = ""
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.1:8b"
    provider_name: str = "local-model"
    timeout: float = 120.0
    temperature: float = 0
    max_retries: int = 0
    retry_delay: float = 0.0
    system_prompt: str = (
        "You are NeuroOntoGen's ontology extraction provider. "
        "Return only JSON matching the requested schema."
    )
    post_json: PostJson = OpenAICompatibleProvider.__dataclass_fields__["post_json"].default

    @classmethod
    def from_env(cls) -> "LocalModelProvider":
        """Build a provider from ``LOCAL_MODEL_*`` environment variables."""
        return cls(
            api_key=os.getenv("LOCAL_MODEL_API_KEY", "").strip(),
            base_url=os.getenv("LOCAL_MODEL_BASE_URL", cls.base_url).strip().rstrip("/"),
            model=os.getenv("LOCAL_MODEL_MODEL", cls.model).strip() or cls.model,
            timeout=float(os.getenv("LOCAL_MODEL_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("LOCAL_MODEL_MAX_RETRIES", str(cls.max_retries))),
            retry_delay=float(os.getenv("LOCAL_MODEL_RETRY_DELAY", str(cls.retry_delay))),
        )

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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self._post_json_with_retries(endpoint, headers, payload)
        return self._extract_message_content(response)
