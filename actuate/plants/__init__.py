"""Plant implementations (control-theory Plant role)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from actuate.domain.protocols import GenerationOutcome, MeteredGenerator


class StubGenerator:
    """Deterministic plant for tests and UI demos without API keys.

    Each call appends a marker so a RuleEvaluator can watch quality climb
    across iterations when a PromptCorrector adds required terms.
    """

    def __init__(self, *, prefix: str = "", delay_seconds: float = 0.0) -> None:
        self.prefix = prefix
        self.delay_seconds = delay_seconds
        self.calls = 0

    async def generate(self, prompt: str, *, context: dict[str, Any]) -> str:
        outcome = await self.generate_with_metadata(prompt, context=context)
        return outcome.text

    async def generate_with_metadata(
        self, prompt: str, *, context: dict[str, Any]
    ) -> GenerationOutcome:
        self.calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        recalled = context.get("retrieved_context", "")
        body = prompt if not self.prefix else f"{self.prefix}\n{prompt}"
        if recalled:
            body = f"{body}\n\n[recalled]\n{recalled}"
        text = f"{body}\n\n[stub-generation #{self.calls}]"
        return GenerationOutcome(
            text=text,
            latency_seconds=self.delay_seconds,
            prompt_tokens=max(1, len(prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
        )


class LiteLLMAdapter:
    """Metered plant over LiteLLM, including OpenAI-compatible custom bases (NVIDIA NIM, etc.)."""

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        api_base: str | None = None,
        api_key: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_base = api_base
        self.api_key = api_key
        self.extra = extra or {}

    async def generate(self, prompt: str, *, context: dict[str, Any]) -> str:
        outcome = await self.generate_with_metadata(prompt, context=context)
        return outcome.text

    async def generate_with_metadata(
        self, prompt: str, *, context: dict[str, Any]
    ) -> GenerationOutcome:
        try:
            from litellm import acompletion
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("litellm is not installed. pip install -e '.[plants]'") from exc

        start = time.monotonic()
        temperature = float(context.get("temperature", self.temperature))
        model = str(context.get("model", self.model))
        messages: list[dict[str, str]] = []
        system = str(context.get("system") or "").strip()
        recalled = context.get("retrieved_context")
        if system:
            messages.append({"role": "system", "content": system})
        if recalled:
            messages.append({"role": "system", "content": f"Useful prior successes:\n{recalled}"})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **self.extra,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "openai"
            kwargs["drop_params"] = True
            if not str(kwargs["model"]).startswith(("openai/", "hosted_vllm/")):
                kwargs["model"] = f"openai/{kwargs['model']}"
        api_key = self.api_key or context.get("api_key")
        if api_key:
            kwargs["api_key"] = api_key
        response = await acompletion(**kwargs)
        choice = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        if prompt_tokens == 0 and completion_tokens == 0:
            prompt_tokens = max(1, len(prompt) // 4)
            completion_tokens = max(1, len(choice) // 4)
        return GenerationOutcome(
            text=choice,
            latency_seconds=time.monotonic() - start,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "openai",
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini", "o3-mini"],
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-3-5-sonnet-latest",
            "anthropic/claude-3-5-haiku-latest",
        ],
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "models": ["gemini/gemini-2.0-flash", "gemini/gemini-1.5-pro", "gemini/gemini-1.5-flash"],
    },
    {
        "id": "groq",
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "models": ["groq/llama-3.3-70b-versatile", "groq/llama-3.1-8b-instant", "groq/mixtral-8x7b-32768"],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "models": [
            "openrouter/openai/gpt-4o-mini",
            "openrouter/anthropic/claude-3.5-sonnet",
            "openrouter/google/gemini-flash-1.5",
            "openrouter/meta-llama/llama-3.1-70b-instruct",
        ],
    },
    {
        "id": "nvidia",
        "name": "NVIDIA NIM (integrate.api.nvidia.com)",
        "env_key": "NVIDIA_API_KEY",
        "api_base": "https://integrate.api.nvidia.com/v1",
        "models": [
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.1-70b-instruct",
            "google/gemma-2-9b-it",
            "mistralai/mistral-7b-instruct-v0.3",
            "microsoft/phi-3-mini-4k-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
        ],
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-compatible",
        "env_key": "CUSTOM_API_KEY",
        "api_base": "",
        "models": ["custom-model"],
    },
    {
        "id": "ollama",
        "name": "Ollama (local)",
        "env_key": None,
        "models": ["ollama/llama3.2", "ollama/mistral", "ollama/qwen2.5"],
    },
    {
        "id": "stub",
        "name": "Stub (offline)",
        "env_key": None,
        "models": ["stub/local"],
    },
]
