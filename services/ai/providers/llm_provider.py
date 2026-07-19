from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMHealth:
    provider: str
    status: str
    model: str
    message: str = ""


@dataclass
class LLMGeneration:
    text: str
    provider: str
    model: str


class LLMProvider(Protocol):
    provider_name: str

    def generate(self, prompt: str) -> LLMGeneration:
        ...

    def health_check(self) -> LLMHealth:
        ...

    def get_model_info(self) -> dict:
        ...
