"""Idempotent bootstrap of workspaces, control systems, specs, and provider bases.

Runs on API startup and via `python -m actuate.persistence.bootstrap`.
Never overwrites API keys the operator already saved.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from actuate.domain.control_system import ControlSystem, Workspace
from actuate.domain.policy import ActuationPolicy, LoopPolicy, RetryStrategyName, SetPoint, StabilityGuard
from actuate.domain.specification import create_specification
from actuate.domain.templates import standard_closed_loop

BOOTSTRAP_WORKSPACE_ID = "actuate000000000000000000000001"
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
OLLAMA_API_BASE = "http://localhost:11434"


def _spec(
    *,
    spec_id: str,
    control_system_id: str,
    plant_name: str,
    plant_params: dict[str, Any],
    sensor_name: str,
    sensor_params: dict[str, Any],
    metadata: dict[str, Any],
    target: float = 0.95,
    max_iterations: int = 6,
) -> Any:
    topology = standard_closed_loop(
        plant_name=plant_name,
        plant_params=plant_params,
        sensor_name=sensor_name,
        sensor_params=sensor_params,
        actuator_name="prompt",
        controller_name="rule",
    )
    created = create_specification(
        control_system_id=control_system_id,
        version_number=1,
        topology=topology,
        policies=LoopPolicy(
            set_point=SetPoint(target=target),
            stability=StabilityGuard(max_iterations=max_iterations, timeout_seconds=180.0),
            actuation=ActuationPolicy(gain=0.6, retry_strategy=RetryStrategyName.EXPONENTIAL),
        ),
        metadata=metadata,
    )
    return replace(created, id=spec_id)


async def seed_store(store: Any) -> Workspace:
    """Fill empty slots only. Safe to call on every process start."""
    workspace = Workspace(id=BOOTSTRAP_WORKSPACE_ID, name="Actuate")
    existing_ws = {row.id for row in await store.list_workspaces()}
    if workspace.id not in existing_ws:
        await store.save_workspace(workspace)

    catalog = [
        (
            ControlSystem(
                id="cs_offline_stub",
                workspace_id=workspace.id,
                name="Offline stub demo",
                description="No API key. Stub plant + rule sensor. Use this to verify the loop.",
            ),
            _spec(
                spec_id="spec_offline_stub",
                control_system_id="cs_offline_stub",
                plant_name="stub",
                plant_params={},
                sensor_name="rule",
                sensor_params={"required_phrases": ["MUST-INCLUDE"], "min_length": 40},
                metadata={
                    "prompt": "Write a short design for a closed-loop AI controller.",
                    "provider": "stub",
                    "model": "stub/local",
                    "bootstrapped": True,
                },
            ),
        ),
        (
            ControlSystem(
                id="cs_nvidia_nim",
                workspace_id=workspace.id,
                name="NVIDIA NIM loop",
                description="OpenAI-compatible NVIDIA Integrate API (build.nvidia.com).",
            ),
            _spec(
                spec_id="spec_nvidia_nim",
                control_system_id="cs_nvidia_nim",
                plant_name="litellm",
                plant_params={
                    "model": "meta/llama-3.1-8b-instruct",
                    "api_base": NVIDIA_API_BASE,
                    "temperature": 0.2,
                },
                sensor_name="rule",
                sensor_params={"min_length": 80},
                metadata={
                    "prompt": "Explain closed-loop feedback control in two paragraphs.",
                    "provider": "nvidia",
                    "model": "meta/llama-3.1-8b-instruct",
                    "bootstrapped": True,
                },
            ),
        ),
        (
            ControlSystem(
                id="cs_custom_endpoint",
                workspace_id=workspace.id,
                name="Custom OpenAI-compatible endpoint",
                description="Paste any chat-completions URL + key on New Run or Settings.",
            ),
            _spec(
                spec_id="spec_custom_endpoint",
                control_system_id="cs_custom_endpoint",
                plant_name="litellm",
                plant_params={"model": "openai/custom-model", "temperature": 0.2},
                sensor_name="rule",
                sensor_params={"min_length": 40},
                metadata={
                    "prompt": "Return a valid JSON object with keys goal, steps, done.",
                    "provider": "custom",
                    "model": "custom-model",
                    "bootstrapped": True,
                },
            ),
        ),
        (
            ControlSystem(
                id="cs_json_refiner",
                workspace_id=workspace.id,
                name="JSON refiner",
                description="Rule sensor requires parseable JSON; prompt actuator retries until it passes.",
            ),
            _spec(
                spec_id="spec_json_refiner",
                control_system_id="cs_json_refiner",
                plant_name="stub",
                plant_params={},
                sensor_name="rule",
                sensor_params={"require_json": True, "min_length": 2},
                metadata={
                    "prompt": '{"goal":"converge","steps":["measure","correct"],"done":true}',
                    "provider": "stub",
                    "model": "stub/local",
                    "bootstrapped": True,
                },
                target=1.0,
            ),
        ),
    ]

    known_systems = {row.id for row in await store.list_control_systems()}
    known_specs = set(await store.list_specification_ids())
    for system, specification in catalog:
        if system.id not in known_systems:
            await store.save_control_system(system)
        if specification.id not in known_specs:
            await store.save_specification(specification)

    keys = await store.get_keys()
    if "nvidia_base" not in keys:
        await store.put_key("nvidia_base", NVIDIA_API_BASE)
    if "ollama_base" not in keys:
        await store.put_key("ollama_base", os.environ.get("OLLAMA_API_BASE", OLLAMA_API_BASE))
    return workspace


async def main() -> None:
    from actuate.runtime_loop import configure_windows_selector_loop

    configure_windows_selector_loop()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("Set DATABASE_URL to bootstrap Postgres.")
    from actuate.persistence.sql_store import SqlRunStore

    store = SqlRunStore(url)
    await store.create_schema()
    workspace = await seed_store(store)
    systems = await store.list_control_systems(workspace.id)
    print(f"Bootstrapped workspace {workspace.name} ({workspace.id})")
    print(f"{len(systems)} control systems, {len(await store.list_specification_ids())} specifications")


def cli() -> None:
    from actuate.runtime_loop import configure_windows_selector_loop

    configure_windows_selector_loop()
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    cli()
