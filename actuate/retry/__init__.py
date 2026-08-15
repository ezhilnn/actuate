"""Plant-call retry wrappers. Order-independent by design — wraps the Plant only."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from actuate.domain.protocols import GenerationOutcome, Generator, MeteredGenerator, RetryAttempt, RetryHandler


class RetryingGenerator:
    def __init__(self, inner: Generator, handler: RetryHandler, *, max_attempts: int = 3) -> None:
        self.inner = inner
        self.handler = handler
        self.max_attempts = max_attempts

    async def generate(self, prompt: str, *, context: dict[str, Any]) -> str:
        outcome = await self.generate_with_metadata(prompt, context=context)
        return outcome.text

    async def generate_with_metadata(
        self, prompt: str, *, context: dict[str, Any]
    ) -> GenerationOutcome:
        last_error: Exception | None = None
        current_prompt = prompt
        current_context = dict(context)
        for attempt in range(1, self.max_attempts + 1):
            try:
                plant: Generator = self.inner
                if isinstance(self.inner, MeteredGenerator):
                    return await self.inner.generate_with_metadata(current_prompt, context=current_context)
                text = await plant.generate(current_prompt, context=current_context)
                return GenerationOutcome(text=text)
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last_error = exc
                if attempt >= self.max_attempts:
                    raise
                prepared: RetryAttempt = self.handler.prepare_attempt(
                    attempt=attempt, prompt=current_prompt, context=current_context, last_error=exc
                )
                current_prompt = prepared.prompt
                current_context = dict(prepared.context)
                if prepared.generator_override is not None:
                    self.inner = prepared.generator_override
                await self.handler.wait_before_retry(attempt)
        raise RuntimeError("retry exhausted") from last_error


class ExponentialRetry:
    def __init__(self, *, base_seconds: float = 0.4) -> None:
        self.base_seconds = base_seconds

    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt:
        return RetryAttempt(prompt=prompt, context=context)

    async def wait_before_retry(self, attempt: int) -> None:
        await asyncio.sleep(self.base_seconds * (2 ** (attempt - 1)))


class DiversityRetry(ExponentialRetry):
    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt:
        updated = dict(context)
        updated["temperature"] = min(1.2, float(updated.get("temperature", 0.2)) + 0.2)
        updated["seed"] = random.randint(1, 10_000)
        return RetryAttempt(prompt=prompt, context=updated)


class TemperatureSweepRetry(ExponentialRetry):
    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt:
        updated = dict(context)
        updated["temperature"] = min(1.0, 0.1 + 0.25 * attempt)
        return RetryAttempt(prompt=prompt, context=updated)


class PromptPerturbationRetry(ExponentialRetry):
    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt:
        suffix = f"\n\n(Retry {attempt}: restate constraints and try a different phrasing.)"
        return RetryAttempt(prompt=prompt + suffix, context=context)


class ModelSwitchRetry(ExponentialRetry):
    def __init__(self, *, fallback_model: str = "gpt-4o-mini", base_seconds: float = 0.4) -> None:
        super().__init__(base_seconds=base_seconds)
        self.fallback_model = fallback_model

    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt:
        updated = dict(context)
        updated["model"] = self.fallback_model
        return RetryAttempt(prompt=prompt, context=updated)
