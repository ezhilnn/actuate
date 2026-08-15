"""Embed Actuate's multi-agent graph in another Python app.

One LiteLLM plant is shared across specialists. Actuate fans work out
in parallel when the DAG allows.
"""

from __future__ import annotations

import asyncio
import os

from actuate.graphs import GraphRunner, templates
from actuate.plants import LiteLLMAdapter


async def main() -> None:
    plant = LiteLLMAdapter(
        model=os.environ.get("ACTUATE_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("NVIDIA_API_KEY", ""),
        api_base=os.environ.get("ACTUATE_API_BASE") or None,
        temperature=0.2,
    )
    graph = next(t for t in templates() if t["id"] == "public_health_ops")
    result = await GraphRunner(plant, max_tokens=80_000).run(
        graph,
        prompt="Coastal town, three boil-water advisories. Cautious public brief. NEED SOURCE if unsure.",
    )
    print(result["status"], result["tokens"], "tokens")
    print(result["output"][:800])


if __name__ == "__main__":
    asyncio.run(main())
