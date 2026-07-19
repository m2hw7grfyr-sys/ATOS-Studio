from __future__ import annotations

import json
import urllib.error
import urllib.request

from config.settings import Settings
from services.ai.providers.llm_provider import LLMGeneration, LLMHealth


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.openai_model or settings.ai_default_model
        self.timeout = settings.openai_timeout_seconds or settings.ai_timeout_seconds

    def health_check(self) -> LLMHealth:
        if not self.settings.openai_enabled:
            return LLMHealth("openai", "not_configured", self.model or "", "openai provider disabled")
        if not self.settings.openai_api_key or not self.model:
            return LLMHealth("openai", "not_configured", self.model or "", "openai api key or model missing")
        return LLMHealth("openai", "available", self.model)

    def generate(self, prompt: str) -> LLMGeneration:
        health = self.health_check()
        if health.status != "available":
            raise RuntimeError(health.message or "openai provider not available")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.settings.ai_temperature,
            "max_tokens": self.settings.ai_max_tokens,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(self.timeout)) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"openai generation failed with HTTP {exc.code}") from exc
        except Exception as exc:
            raise RuntimeError("openai generation failed") from exc
        choices = body.get("choices") or []
        text = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "")
        if not text.strip():
            raise RuntimeError("openai returned empty response")
        return LLMGeneration(text=text, provider="openai", model=self.model)

    def get_model_info(self) -> dict:
        return {"provider": "openai", "model": self.model, "enabled": self.settings.openai_enabled}
