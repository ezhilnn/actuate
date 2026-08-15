"""Turn graph runs into reward trajectories for SFT / DPO / RL trainers.

Actuate scores; the caller updates model weights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from actuate.domain.protocols import Generator
from actuate.graphs.builder import Graph, as_graph_dict
from actuate.graphs.runner import GraphRunner


@dataclass
class Trajectory:
    prompt: str
    completion: str
    reward: float
    feedback: str = ""
    status: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    tokens: int = 0
    run_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def trajectories_from_run(result: dict[str, Any]) -> list[Trajectory]:
    """One overall trajectory plus one row per node that produced text."""
    feedback_bits: list[str] = []
    for trace in result.get("traces") or []:
        for fb in trace.get("feedback") or []:
            if fb:
                feedback_bits.append(str(fb))
    overall = Trajectory(
        prompt=str(result.get("prompt") or ""),
        completion=str(result.get("output") or ""),
        reward=float(result.get("reward") or 0.0),
        feedback="\n".join(feedback_bits),
        status=str(result.get("status") or ""),
        scores={str(k): float(v) for k, v in (result.get("judge_scores") or {}).items()},
        tokens=int(result.get("tokens") or 0),
        run_id=str(result.get("id") or ""),
    )
    rows = [overall]
    for trace in result.get("traces") or []:
        outs = trace.get("outputs") or []
        if not outs:
            continue
        scores = [float(s) for s in (trace.get("scores") or [])]
        node_reward = scores[-1] if scores else overall.reward
        rows.append(
            Trajectory(
                prompt=str((trace.get("inputs") or [result.get("prompt")])[-1] or ""),
                completion=str(outs[-1]),
                reward=float(node_reward),
                feedback=str((trace.get("feedback") or [""])[-1] if trace.get("feedback") else ""),
                status=str(result.get("status") or ""),
                scores={str(trace.get("node_id")): float(node_reward)} if scores else {},
                tokens=int(trace.get("tokens") or 0),
                run_id=str(result.get("id") or ""),
            )
        )
    return rows


def dpo_pairs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair higher-reward completions as chosen vs lower as rejected (same prompt)."""
    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_prompt.setdefault(str(run.get("prompt") or ""), []).append(run)
    pairs: list[dict[str, Any]] = []
    for prompt, group in by_prompt.items():
        ranked = sorted(group, key=lambda r: float(r.get("reward") or 0), reverse=True)
        if len(ranked) < 2:
            continue
        best, worst = ranked[0], ranked[-1]
        if float(best.get("reward") or 0) <= float(worst.get("reward") or 0):
            continue
        pairs.append(
            {
                "prompt": prompt,
                "chosen": best.get("output") or "",
                "rejected": worst.get("output") or "",
                "chosen_reward": float(best.get("reward") or 0),
                "rejected_reward": float(worst.get("reward") or 0),
            }
        )
    return pairs


class GraphEnv:
    """Minimal gym-style env: prompt in, Trajectory (reward) out."""

    def __init__(
        self,
        graph: Graph | dict[str, Any],
        generator: Generator,
        *,
        max_tokens: int = 80_000,
    ) -> None:
        self.graph = as_graph_dict(graph)
        self.runner = GraphRunner(generator, max_tokens=max_tokens)

    async def step(self, prompt: str) -> Trajectory:
        result = await self.runner.run(self.graph, prompt=prompt)
        return trajectories_from_run(result)[0]

    async def collect(self, prompts: Iterable[str]) -> list[Trajectory]:
        out: list[Trajectory] = []
        for prompt in prompts:
            out.append(await self.step(prompt))
        return out
