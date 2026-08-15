"""Embed Actuate as a closed-loop quality controller in another Python app.

You pass plant credentials (model + API key). Actuate calls the LLM.
"""

from __future__ import annotations

import asyncio
import os

from actuate.domain.policy import LoopPolicy, SetPoint, StabilityGuard
from actuate.domain.specification import create_specification
from actuate.domain.templates import standard_closed_loop
from actuate.engine import ExecutionEngine
from actuate.plugins import register_builtins


async def main() -> None:
    spec = create_specification(
        control_system_id="embed-demo",
        version_number=1,
        topology=standard_closed_loop(
            plant_name="litellm",
            plant_params={
                "model": os.environ.get("ACTUATE_MODEL", "gpt-4o-mini"),
                "api_key": os.environ.get("OPENAI_API_KEY") or os.environ.get("NVIDIA_API_KEY", ""),
                "api_base": os.environ.get("ACTUATE_API_BASE") or None,
                "temperature": 0.2,
            },
            sensor_name="rule",
            sensor_params={"min_length": 80},
        ),
        policies=LoopPolicy(
            set_point=SetPoint(target=0.9),
            stability=StabilityGuard(max_iterations=4, min_iterations=1),
        ),
    )
    run = await ExecutionEngine().run(
        spec,
        registry=register_builtins(),
        initial_prompt="Explain why closed-loop control beats generate-once for public briefs.",
    )
    print("run", run.id)


if __name__ == "__main__":
    asyncio.run(main())
