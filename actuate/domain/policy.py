"""actuate.domain.policy — decomposed control policy, one value object per
control concept (not a single flat bag of unrelated fields).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from actuate.domain.exceptions import PolicyViolationError


class SetPoint(BaseModel):
    """The target — literally control theory's setpoint."""

    target: float = Field(default=0.95, ge=0.0, le=1.0)
    scope: str = "aggregate"  # reserved; see the frozen architecture §8 (open question)


class ConvergenceCriteria(BaseModel):
    """What "no longer meaningfully improving" means."""

    min_improvement: float = Field(default=0.01, ge=0.0)
    patience: int = Field(default=2, ge=1)


class StabilityGuard(BaseModel):
    """Safety bounds, independent of any one control algorithm."""

    max_iterations: int = Field(default=8, ge=1)
    min_iterations: int = Field(default=1, ge=1)
    timeout_seconds: float | None = Field(default=120.0, ge=0.0)


class RetryStrategyName(str, Enum):
    NONE = "none"
    EXPONENTIAL = "exponential"
    DIVERSITY = "diversity"
    TEMPERATURE_SWEEP = "temperature_sweep"
    MODEL_SWITCH = "model_switch"
    PROMPT_PERTURBATION = "prompt_perturbation"


class ActuationPolicy(BaseModel):
    """How aggressively a correction responds, and how Plant-call
    failures are retried.
    """

    gain: float = Field(default=0.5, ge=0.0, le=1.0)
    retry_strategy: RetryStrategyName = RetryStrategyName.EXPONENTIAL


class LoopPolicy(BaseModel):
    """The composed policy hanging off a Specification."""

    set_point: SetPoint = Field(default_factory=SetPoint)
    convergence: ConvergenceCriteria = Field(default_factory=ConvergenceCriteria)
    stability: StabilityGuard = Field(default_factory=StabilityGuard)
    actuation: ActuationPolicy = Field(default_factory=ActuationPolicy)

    @model_validator(mode="after")
    def _validate_consistency(self) -> LoopPolicy:
        if self.set_point.target < self.convergence.min_improvement:
            raise PolicyViolationError(
                f"set_point.target ({self.set_point.target}) is smaller than "
                f"convergence.min_improvement ({self.convergence.min_improvement}); "
                "the run would converge on iteration 1 regardless of quality."
            )
        return self
