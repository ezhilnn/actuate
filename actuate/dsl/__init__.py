"""YAML compiler: definition file → Specification + standard topology."""

from __future__ import annotations

from typing import Any

from actuate.domain.policy import (
    ActuationPolicy,
    ConvergenceCriteria,
    LoopPolicy,
    RetryStrategyName,
    SetPoint,
    StabilityGuard,
)
from actuate.domain.specification import Specification, create_specification
from actuate.domain.templates import standard_closed_loop


def compile_loop(definition: dict[str, Any], *, control_system_id: str, version_number: int = 1) -> Specification:
    plant = definition.get("plant") or {}
    sensor = definition.get("sensor") or {}
    actuator = definition.get("actuator") or {}
    policy = definition.get("policy") or {}
    topology = standard_closed_loop(
        plant_name=plant.get("name", "stub"),
        plant_params=plant.get("params") or {},
        sensor_name=sensor.get("name", "rule"),
        sensor_params=sensor.get("params") or {},
        actuator_name=actuator.get("name", "prompt"),
        actuator_params=actuator.get("params") or {},
        fusion_name=(definition.get("fusion") or {}).get("name", "single"),
        controller_name=(definition.get("controller") or {}).get("name", "rule"),
    )
    retry_name = str(policy.get("retry_strategy", "exponential"))
    try:
        retry = RetryStrategyName(retry_name)
    except ValueError:
        retry = RetryStrategyName.EXPONENTIAL
    policies = LoopPolicy(
        set_point=SetPoint(target=float(policy.get("target_score", 0.95))),
        convergence=ConvergenceCriteria(
            min_improvement=float(policy.get("min_improvement", 0.01)),
            patience=int(policy.get("patience", 2)),
        ),
        stability=StabilityGuard(
            max_iterations=int(policy.get("max_iterations", 8)),
            timeout_seconds=policy.get("timeout_seconds", 120.0),
        ),
        actuation=ActuationPolicy(
            gain=float(policy.get("gain", 0.5)),
            retry_strategy=retry,
        ),
    )
    return create_specification(
        control_system_id=control_system_id,
        version_number=version_number,
        topology=topology,
        policies=policies,
        metadata={"name": definition.get("name", "unnamed"), "initial_prompt": definition.get("prompt", "")},
    )


def load_yaml(text: str) -> dict[str, Any]:
    import yaml

    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("YAML root must be a mapping.")
    return loaded
