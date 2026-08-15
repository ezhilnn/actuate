"""Actuator implementations (Corrector role)."""

from __future__ import annotations

from typing import Any

from actuate.domain.protocols import CorrectionOutcome, EvaluationOutcome, MemoryRetriever


class PromptCorrector:
    """Mutates the next Plant input. Optionally grounds the rewrite in recalled successes."""

    def __init__(self, *, retriever: MemoryRetriever | None = None) -> None:
        self.retriever = retriever

    async def correct(
        self,
        *,
        prompt: str,
        output: str,
        evaluation: EvaluationOutcome,
        gain: float,
        context: dict[str, Any],
    ) -> CorrectionOutcome:
        examples = ""
        if self.retriever is not None:
            records = await self.retriever.recall(prompt, top_k=3)
            if records:
                examples = "\n".join(f"- {r.text}" for r in records)
                context["retrieved_context"] = examples
        instruction = evaluation.feedback or "Improve quality toward the setpoint."
        if gain < 0.34:
            revised = (
                f"{prompt}\n\n[low-gain correction] Address: {instruction}"
            )
        elif gain < 0.67:
            revised = (
                f"{prompt}\n\nRevise the previous attempt. Feedback: {instruction}\n"
                f"Previous output (excerpt): {output[:400]}"
            )
            if examples:
                revised += f"\n\nWorked examples:\n{examples}"
        else:
            revised = (
                f"You must fully satisfy this feedback: {instruction}\n\n"
                f"Original task:\n{prompt}\n"
            )
            if examples:
                revised += f"\nSuccessful prior trajectories:\n{examples}\n"
        return CorrectionOutcome(
            action_kind="input_mutation",
            revised_prompt=revised,
            notes=f"prompt correction at gain={gain}",
        )


class OutputCorrector:
    async def correct(
        self,
        *,
        prompt: str,
        output: str,
        evaluation: EvaluationOutcome,
        gain: float,
        context: dict[str, Any],
    ) -> CorrectionOutcome:
        return CorrectionOutcome(
            action_kind="input_mutation",
            revised_prompt=(
                f"{prompt}\n\nRepair this output rather than regenerating from scratch:\n{output}\n\n"
                f"Issues: {evaluation.feedback}"
            ),
            notes="output-repair actuation",
        )


class ContextCorrector:
    async def correct(
        self,
        *,
        prompt: str,
        output: str,
        evaluation: EvaluationOutcome,
        gain: float,
        context: dict[str, Any],
    ) -> CorrectionOutcome:
        context["temperature"] = min(1.2, float(context.get("temperature", 0.2)) + 0.15 * gain)
        return CorrectionOutcome(
            action_kind="policy_retune",
            policy_adjustment={"temperature": context["temperature"]},
            revised_prompt=prompt,
            notes="raised temperature for diversity",
        )


class StrategyCorrector:
    async def correct(
        self,
        *,
        prompt: str,
        output: str,
        evaluation: EvaluationOutcome,
        gain: float,
        context: dict[str, Any],
    ) -> CorrectionOutcome:
        step = int(context.get("strategy_step", 0)) + 1
        context["strategy_step"] = step
        prefixes = (
            "Think step by step.\n\n",
            "Explore two alternative approaches, then pick the better one.\n\n",
            "Critique your plan, then produce a final answer.\n\n",
        )
        prefix = prefixes[min(step, len(prefixes)) - 1]
        return CorrectionOutcome(
            action_kind="input_mutation",
            revised_prompt=prefix + prompt,
            notes=f"strategy escalation step={step}",
        )
