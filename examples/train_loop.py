"""Collect reward trajectories from an Actuate graph for a training loop.

The graph judges the plant. Your trainer consumes Trajectory.reward
(and optional DPO pairs). Weights stay in your training stack.
"""

from __future__ import annotations

import asyncio

from actuate import Agents, Graph, GraphEnv, GraphRunner, agent, dpo_pairs, trajectories_from_run
from actuate.plants import StubGenerator


async def main() -> None:
    writer = agent(
        "policy_writer",
        title="Policy writer",
        system="Write a one-paragraph policy memo. First sentence is the decision question.",
    )
    graph = (
        Graph("train-lab", target_score=0.5, max_passes=1)
        .add("in", Agents.ingress)
        .add("writer", writer)
        .add("judge", Agents.judge_accuracy)
        .add("out", Agents.egress)
        .connect("in", "writer", "judge", "out")
    )
    env = GraphEnv(graph, StubGenerator(), max_tokens=20_000)
    prompts = [
        "Should the clinic send SMS reminders 48h before appointments?",
        "Draft a one-line rule for no-show risk flags.",
    ]
    rows = await env.collect(prompts)
    for row in rows:
        print(f"reward={row.reward:.3f} status={row.status} tokens={row.tokens}")
        print(row.completion[:240], "\n")

    plant = StubGenerator()
    runs = []
    for prompt in prompts:
        runs.append(await GraphRunner(plant, max_tokens=20_000).run(graph, prompt=prompt))
    pairs = dpo_pairs(runs)
    print("dpo pairs", len(pairs), "trajectories", len(trajectories_from_run(runs[0])))


if __name__ == "__main__":
    asyncio.run(main())
