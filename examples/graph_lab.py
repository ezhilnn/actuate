"""Embed Actuate's multi-agent graph in another Python app."""

from __future__ import annotations

import asyncio
import os

from actuate import Agents, Graph, GraphRunner
from actuate.plants import LiteLLMAdapter


async def main() -> None:
    plant = LiteLLMAdapter(
        model=os.environ.get("ACTUATE_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("NVIDIA_API_KEY", ""),
        api_base=os.environ.get("ACTUATE_API_BASE") or None,
        temperature=0.2,
    )
    graph = (
        Graph("health-brief", target_score=0.8, max_passes=2)
        .add("in", Agents.ingress)
        .add("research", Agents.researcher)
        .add("judge", Agents.judge_accuracy)
        .add("out", Agents.egress)
        .connect("in", "research", "judge", "out")
    )
    result = await GraphRunner(plant, max_tokens=80_000).run(
        graph,
        prompt="Coastal town, three boil-water advisories. Cautious public brief. NEED SOURCE if unsure.",
    )
    print(result["status"], result["reward"], result["tokens"], "tokens")
    print(result["output"][:800])


if __name__ == "__main__":
    asyncio.run(main())
