from __future__ import annotations

import json
import urllib.error
import urllib.request

from config.settings import Settings
from services.ai.providers.llm_provider import LLMGeneration, LLMHealth


class LocalLLMProvider:
    provider_name = "local"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_type = settings.local_llm_type.lower()
        self.model = settings.local_llm_model or settings.ai_default_model
        self.timeout = settings.local_llm_timeout_seconds

    def _configured(self) -> bool:
        return bool(self.settings.local_llm_url and self.model and self.llm_type in {"ollama", "vllm"})

    def health_check(self) -> LLMHealth:
        if not self._configured():
            return LLMHealth("local", "not_configured", self.model or "", "local llm is not configured")
        try:
            if self.llm_type == "ollama":
                request = urllib.request.Request(f"{self.settings.local_llm_url.rstrip('/')}/api/tags")
            else:
                request = urllib.request.Request(f"{self.settings.local_llm_url.rstrip('/')}/v1/models")
            with urllib.request.urlopen(request, timeout=min(float(self.timeout), 5.0)) as response:
                if 200 <= response.status < 300:
                    return LLMHealth("local", "available", self.model)
        except urllib.error.URLError:
            return LLMHealth("local", "unavailable", self.model, "local llm endpoint unavailable")
        except Exception:
            return LLMHealth("local", "error", self.model, "local llm health check failed")
        return LLMHealth("local", "error", self.model, "local llm returned non-success status")

    def generate(self, prompt: str) -> LLMGeneration:
        if not self._configured():
            raise RuntimeError("local llm is not configured")
        if self.llm_type == "ollama":
            url = f"{self.settings.local_llm_url.rstrip('/')}/api/generate"
            payload = {"model": self.model, "prompt": prompt, "stream": False, "format": self.settings.ai_output_format}
            response_key = "response"
        else:
            url = f"{self.settings.local_llm_url.rstrip('/')}/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.settings.ai_temperature,
                "max_tokens": self.settings.ai_max_tokens,
            }
            response_key = "choices"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(self.timeout)) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("local llm generation failed") from exc
        if response_key == "response":
            text = str(body.get("response") or "")
        else:
            choices = body.get("choices") or []
            text = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "")
        if not text.strip():
            raise RuntimeError("local llm returned empty response")
        return LLMGeneration(text=text, provider="local", model=self.model)

    def get_model_info(self) -> dict:
        return {"provider": "local", "type": self.llm_type, "model": self.model}
