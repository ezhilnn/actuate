"""Register every built-in capability into a CapabilityRegistry."""

from __future__ import annotations

from actuate.actuators import ContextCorrector, OutputCorrector, PromptCorrector, StrategyCorrector
from actuate.domain.capability import CapabilityDescriptor, CapabilityKinds
from actuate.domain.registry import CapabilityRegistry
from actuate.engine.controller import RuleBasedController
from actuate.engine.fusion import SingleSignalFusion, WeightedMeanFusion, WorstCaseFusion
from actuate.engine.pid import PIDController
from actuate.engine.scheduler import SequentialScheduler
from actuate.plants import LiteLLMAdapter, StubGenerator
from actuate.retry import (
    DiversityRetry,
    ExponentialRetry,
    ModelSwitchRetry,
    PromptPerturbationRetry,
    TemperatureSweepRetry,
)
from actuate.sensors import LLMJudgeEvaluator, RuleEvaluator, SimilarityEvaluator


def _desc(
    kind: str,
    name: str,
    description: str,
    *,
    config_schema: dict[str, object] | None = None,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        kind=kind,
        name=name,
        version="0.1.0",
        author="Actuate",
        description=description,
        config_schema=config_schema or {},
        compatible_with=("actuate>=0.1",),
    )


def register_builtins(registry: CapabilityRegistry | None = None) -> CapabilityRegistry:
    registry = registry or CapabilityRegistry()

    registry.register(
        _desc(CapabilityKinds.PLANT, "stub", "Offline deterministic plant for demos and tests."),
        lambda **params: StubGenerator(**params),
    )
    registry.register(
        _desc(
            CapabilityKinds.PLANT,
            "litellm",
            "LiteLLM plant — OpenAI, Anthropic, Gemini, Groq, OpenRouter, Ollama.",
            config_schema={"model": "str", "temperature": "float"},
        ),
        lambda **params: LiteLLMAdapter(**params),
    )

    registry.register(
        _desc(CapabilityKinds.SENSOR, "rule", "Rule / schema / phrase evaluator."),
        lambda **params: RuleEvaluator(**params),
    )
    registry.register(
        _desc(CapabilityKinds.SENSOR, "llm_judge", "LLM-as-judge evaluator."),
        lambda **params: LLMJudgeEvaluator(**params),
    )
    registry.register(
        _desc(CapabilityKinds.SENSOR, "similarity", "Token-cosine similarity evaluator."),
        lambda **params: SimilarityEvaluator(**params),
    )

    registry.register(
        _desc(CapabilityKinds.ACTUATOR, "prompt", "Prompt-mutation actuator."),
        lambda **params: PromptCorrector(**params),
    )
    registry.register(
        _desc(CapabilityKinds.ACTUATOR, "output", "Output-repair actuator."),
        lambda **params: OutputCorrector(**params),
    )
    registry.register(
        _desc(CapabilityKinds.ACTUATOR, "context", "Context / temperature actuator."),
        lambda **params: ContextCorrector(**params),
    )
    registry.register(
        _desc(CapabilityKinds.ACTUATOR, "strategy", "Reasoning-strategy escalation actuator."),
        lambda **params: StrategyCorrector(**params),
    )

    registry.register(
        _desc(CapabilityKinds.CONTROLLER, "rule", "First-available rule-based controller."),
        lambda **_params: RuleBasedController(),
    )
    registry.register(
        _desc(CapabilityKinds.CONTROLLER, "pid", "PID controller over the error signal."),
        lambda **params: PIDController(**params),
    )

    registry.register(
        _desc(CapabilityKinds.SIGNAL_FUSION_STRATEGY, "single", "Pass through the first observation."),
        lambda **_params: SingleSignalFusion(),
    )
    registry.register(
        _desc(CapabilityKinds.SIGNAL_FUSION_STRATEGY, "weighted_mean", "Weighted mean of observations."),
        lambda **params: WeightedMeanFusion(**params),
    )
    registry.register(
        _desc(CapabilityKinds.SIGNAL_FUSION_STRATEGY, "worst_case", "Min score across observations."),
        lambda **_params: WorstCaseFusion(),
    )

    registry.register(
        _desc(CapabilityKinds.SCHEDULER, "sequential", "Run node tasks one after another."),
        lambda **_params: SequentialScheduler(),
    )

    registry.register(
        _desc(CapabilityKinds.RETRY_HANDLER, "exponential", "Exponential backoff retry."),
        lambda **params: ExponentialRetry(**params),
    )
    registry.register(
        _desc(CapabilityKinds.RETRY_HANDLER, "diversity", "Diversity (temperature + seed) retry."),
        lambda **params: DiversityRetry(**params),
    )
    registry.register(
        _desc(CapabilityKinds.RETRY_HANDLER, "temperature_sweep", "Sweep temperature on retry."),
        lambda **params: TemperatureSweepRetry(**params),
    )
    registry.register(
        _desc(CapabilityKinds.RETRY_HANDLER, "model_switch", "Switch to a fallback model on retry."),
        lambda **params: ModelSwitchRetry(**params),
    )
    registry.register(
        _desc(CapabilityKinds.RETRY_HANDLER, "prompt_perturbation", "Perturb the prompt on retry."),
        lambda **params: PromptPerturbationRetry(**params),
    )
    return registry
