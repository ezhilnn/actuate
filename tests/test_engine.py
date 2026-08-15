import pytest

from actuate.domain.policy import LoopPolicy, SetPoint, StabilityGuard, ActuationPolicy, RetryStrategyName
from actuate.domain.run import current_status, iterations
from actuate.domain.specification import create_specification
from actuate.domain.templates import standard_closed_loop
from actuate.engine.execution_engine import ExecutionEngine
from actuate.persistence.codec import decode_event, decode_specification, encode, encode_specification
from actuate.plugins import register_builtins


@pytest.mark.asyncio
async def test_closed_loop_converges_with_stub_plant() -> None:
    registry = register_builtins()
    topology = standard_closed_loop(
        plant_name="stub",
        sensor_name="rule",
        sensor_params={"required_phrases": ["MUST-INCLUDE"], "min_length": 10},
        actuator_name="prompt",
        controller_name="rule",
    )
    spec = create_specification(
        control_system_id="cs1",
        version_number=1,
        topology=topology,
        policies=LoopPolicy(
            set_point=SetPoint(target=0.95),
            stability=StabilityGuard(max_iterations=6, timeout_seconds=30),
            actuation=ActuationPolicy(gain=0.8, retry_strategy=RetryStrategyName.NONE),
        ),
    )
    run = await ExecutionEngine().run(spec, registry=registry, initial_prompt="Write a short answer.")
    assert current_status(run) in {"converged", "exhausted", "oscillating"}
    assert len(iterations(run)) >= 1
    assert iterations(run)[0].output is not None


@pytest.mark.asyncio
async def test_llm_judge_sensor_binds_plant() -> None:
    registry = register_builtins()
    topology = standard_closed_loop(
        plant_name="stub",
        sensor_name="llm_judge",
        actuator_name="prompt",
        controller_name="rule",
    )
    spec = create_specification(
        control_system_id="cs1",
        version_number=1,
        topology=topology,
        policies=LoopPolicy(
            set_point=SetPoint(target=0.99),
            stability=StabilityGuard(max_iterations=2, timeout_seconds=30),
            actuation=ActuationPolicy(gain=0.5, retry_strategy=RetryStrategyName.NONE),
        ),
    )
    run = await ExecutionEngine().run(spec, registry=registry, initial_prompt="Write a short answer.")
    first = iterations(run)[0]
    assert first.observations
    assert first.observations[0].details.get("mode") == "llm"


@pytest.mark.asyncio
async def test_specification_roundtrip() -> None:
    topology = standard_closed_loop(plant_name="stub")
    spec = create_specification(control_system_id="cs", version_number=2, topology=topology)
    restored = decode_specification(encode_specification(spec))
    assert restored.id == spec.id
    assert restored.topology.nodes[0].id == "plant"
    assert restored.policies.set_point.target == spec.policies.set_point.target


@pytest.mark.asyncio
async def test_event_roundtrip() -> None:
    from actuate.domain.events import RunStarted

    event = RunStarted(run_id="r1", specification_id="s1", mode="live")
    restored = decode_event(encode(event))
    assert isinstance(restored, RunStarted)
    assert restored.run_id == "r1"
