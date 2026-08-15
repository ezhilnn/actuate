"""Sensor implementations (Evaluator role)."""

from __future__ import annotations

import json
import re
from typing import Any

from actuate.domain.protocols import EvaluationOutcome


class RuleEvaluator:
    """Structural checks: required phrases, regex, JSON, min length."""

    def __init__(
        self,
        *,
        required_phrases: list[str] | None = None,
        regex: str | None = None,
        require_json: bool = False,
        min_length: int = 0,
    ) -> None:
        self.required_phrases = required_phrases or []
        self.regex = regex
        self.require_json = require_json
        self.min_length = min_length

    async def evaluate(
        self, *, prompt: str, output: str, context: dict[str, Any]
    ) -> EvaluationOutcome:
        checks: list[tuple[str, bool]] = []
        if self.min_length:
            checks.append(("min_length", len(output) >= self.min_length))
        for phrase in self.required_phrases:
            checks.append((f"phrase:{phrase}", phrase.lower() in output.lower()))
        if self.regex:
            checks.append(("regex", re.search(self.regex, output) is not None))
        if self.require_json:
            try:
                json.loads(output)
                checks.append(("json", True))
            except json.JSONDecodeError:
                checks.append(("json", False))
        if not checks:
            checks.append(("non_empty", bool(output.strip())))
        passed_count = sum(1 for _, ok in checks if ok)
        score = passed_count / len(checks)
        failed = [name for name, ok in checks if not ok]
        feedback = "All rule checks passed." if not failed else "Failed: " + ", ".join(failed)
        return EvaluationOutcome(
            score=score,
            passed=score >= 1.0,
            feedback=feedback,
            details={"checks": {name: ok for name, ok in checks}, "prompt_chars": len(prompt)},
        )


class LLMJudgeEvaluator:
    """Scores output with a second LLM call. Falls back to heuristic if no plant is bound."""

    def __init__(self, *, plant: Any | None = None, rubric: str = "correctness, completeness, clarity") -> None:
        self.plant = plant
        self.rubric = rubric

    async def evaluate(
        self, *, prompt: str, output: str, context: dict[str, Any]
    ) -> EvaluationOutcome:
        if self.plant is None:
            length_score = min(1.0, len(output) / max(80, len(prompt)))
            return EvaluationOutcome(
                score=round(length_score, 3),
                passed=length_score >= 0.8,
                feedback="Heuristic judge (no plant bound): length vs prompt.",
                details={"mode": "heuristic", "rubric": self.rubric},
            )
        judge_prompt = (
            f"Score the assistant output from 0.0 to 1.0 on {self.rubric}.\n"
            "Reply with JSON {\"score\": float, \"feedback\": str} only.\n\n"
            f"USER PROMPT:\n{prompt}\n\nOUTPUT:\n{output}"
        )
        raw = await self.plant.generate(judge_prompt, context=context)
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            parsed = json.loads(raw[start:end])
            score = float(parsed.get("score", 0.0))
            feedback = str(parsed.get("feedback", raw))
        except (ValueError, json.JSONDecodeError):
            score = 0.0
            feedback = raw
        score = max(0.0, min(1.0, score))
        return EvaluationOutcome(score=score, passed=score >= 0.8, feedback=feedback, details={"mode": "llm"})


class SimilarityEvaluator:
    """Embedding cosine similarity against a reference string."""

    def __init__(self, *, reference: str = "", threshold: float = 0.7) -> None:
        self.reference = reference
        self.threshold = threshold

    async def evaluate(
        self, *, prompt: str, output: str, context: dict[str, Any]
    ) -> EvaluationOutcome:
        target = self.reference or prompt
        score = _token_cosine(output, target)
        return EvaluationOutcome(
            score=score,
            passed=score >= self.threshold,
            feedback=f"Similarity {score:.3f} vs threshold {self.threshold}.",
            details={"method": "token-cosine"},
        )


def _token_cosine(left: str, right: str) -> float:
    def bag(text: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            counts[token] = counts.get(token, 0) + 1
        return counts

    a, b = bag(left), bag(right)
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = sum(v * v for v in a.values()) ** 0.5
    mag_b = sum(v * v for v in b.values()) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
