"""Execute a user-designed agent graph until judges pass or passes exhaust."""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from actuate.domain.protocols import Generator, MeteredGenerator
from actuate.graphs.catalog import agent_by_id

LogFn = Callable[[dict[str, Any]], Awaitable[None]]


def topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> list[str]:
    ids = {n["id"] for n in nodes}
    incoming: dict[str, int] = {i: 0 for i in ids}
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["source"] not in ids or edge["target"] not in ids:
            continue
        adj[edge["source"]].append(edge["target"])
        incoming[edge["target"]] += 1
    queue = deque([i for i, c in incoming.items() if c == 0])
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in adj[node]:
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(ids):
        raise ValueError("Graph has a cycle. Connect agents as a DAG; judges already loop locally.")
    return order


def _parents(node_id: str, edges: list[dict[str, str]]) -> list[str]:
    return [e["source"] for e in edges if e["target"] == node_id]


def _parse_judge(raw: str) -> tuple[float, str, bool]:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        score = float(parsed.get("score", 0.0))
        feedback = str(parsed.get("feedback", raw))
        passed = bool(parsed.get("passed", score >= 0.8))
        return max(0.0, min(1.0, score)), feedback, passed
    except (ValueError, json.JSONDecodeError, TypeError):
        return 0.0, raw, False


class GraphRunner:
    def __init__(self, generator: Generator, *, log: LogFn | None = None) -> None:
        self.generator = generator
        self.log = log

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.log:
            await self.log(payload)

    async def _call(
        self, *, system: str, prompt: str, context: dict[str, Any]
    ) -> tuple[str, float, int]:
        ctx = dict(context)
        if system:
            ctx["system"] = system
        start = time.monotonic()
        if isinstance(self.generator, MeteredGenerator):
            outcome = await self.generator.generate_with_metadata(prompt, context=ctx)
            return outcome.text, outcome.latency_seconds, outcome.prompt_tokens + outcome.completion_tokens
        text = await self.generator.generate(prompt, context=ctx)
        return text, time.monotonic() - start, 0

    async def run(
        self,
        graph: dict[str, Any],
        *,
        prompt: str,
        context: dict[str, Any] | None = None,
        run_id: str | None = None,
        overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or uuid.uuid4().hex
        nodes = {n["id"]: n for n in graph["nodes"]}
        edges = list(graph.get("edges") or [])
        order = topological_order(list(nodes.values()), edges)
        target = float(graph.get("target_score") or 0.85)
        max_passes = int(graph.get("max_passes") or 4)
        traces: dict[str, dict[str, Any]] = {
            nid: {
                "node_id": nid,
                "agent": nodes[nid]["agent"],
                "inputs": [],
                "outputs": [],
                "scores": [],
                "feedback": [],
                "latency_seconds": 0.0,
                "tokens": 0,
                "passes": 0,
                "steps": [],
            }
            for nid in nodes
        }
        ctx = dict(context or {})
        overrides = overrides or {}
        started = time.monotonic()
        await self._emit({"kind": "GraphStarted", "run_id": run_id, "graph": graph.get("id")})

        async def inputs_for(nid: str) -> list[str]:
            if nid in overrides:
                return [overrides[nid]]
            parents = _parents(nid, edges)
            if not parents:
                return [prompt]
            collected: list[str] = []
            for parent in parents:
                outs = traces[parent]["outputs"]
                collected.append(outs[-1] if outs else "")
            return [c for c in collected if c] or [prompt]

        for pass_index in range(1, max_passes + 1):
            all_judges_ok = True
            for nid in order:
                node = nodes[nid]
                spec = agent_by_id(node["agent"])
                incoming = await inputs_for(nid)
                traces[nid]["inputs"].append("\n\n---\n\n".join(incoming))
                traces[nid]["passes"] = pass_index
                await self._emit({"kind": "NodeStarted", "run_id": run_id, "node_id": nid, "agent": node["agent"]})

                if spec["kind"] == "io" and spec["id"] == "ingress":
                    text = prompt
                    latency, tokens = 0.0, 0
                elif spec["kind"] == "io" and spec["id"] == "egress":
                    text = incoming[-1] if incoming else prompt
                    latency, tokens = 0.0, 0
                elif spec["kind"] == "judge":
                    judge_prompt = (
                        f"User goal:\n{prompt}\n\nCandidate:\n{incoming[-1] if incoming else ''}\n"
                        f"Target score: {target}"
                    )
                    text, latency, tokens = await self._call(
                        system=spec["system"], prompt=judge_prompt, context=ctx
                    )
                    score, feedback, passed = _parse_judge(text)
                    traces[nid]["scores"].append(score)
                    traces[nid]["feedback"].append(feedback)
                    if score < target or not passed:
                        all_judges_ok = False
                        for parent in _parents(nid, edges):
                            traces[parent]["feedback"].append(feedback)
                else:
                    revision = ""
                    if traces[nid]["feedback"]:
                        revision = "\n\nJudge feedback to address:\n" + traces[nid]["feedback"][-1]
                    user_blob = "\n\n".join(incoming) + revision
                    text, latency, tokens = await self._call(
                        system=spec["system"], prompt=user_blob, context=ctx
                    )

                traces[nid]["steps"] = traces[nid].get("steps") or []
                traces[nid]["steps"].append(
                    {
                        "pass": pass_index,
                        "input": traces[nid]["inputs"][-1],
                        "output": text,
                        "score": traces[nid]["scores"][-1] if spec["kind"] == "judge" and traces[nid]["scores"] else None,
                        "feedback": traces[nid]["feedback"][-1] if traces[nid]["feedback"] else None,
                        "latency_seconds": latency,
                        "tokens": tokens,
                    }
                )
                traces[nid]["outputs"].append(text)
                traces[nid]["latency_seconds"] += latency
                traces[nid]["tokens"] += tokens
                await self._emit(
                    {
                        "kind": "NodeCompleted",
                        "run_id": run_id,
                        "node_id": nid,
                        "agent": node["agent"],
                        "pass": pass_index,
                        "output_preview": text[:280],
                    }
                )

            if all_judges_ok:
                status = "converged"
                break
        else:
            status = "exhausted"

        egress_ids = [n["id"] for n in graph["nodes"] if n["agent"] == "egress"]
        final = ""
        if egress_ids and traces[egress_ids[-1]]["outputs"]:
            final = traces[egress_ids[-1]]["outputs"][-1]
        elif order:
            final = traces[order[-1]]["outputs"][-1] if traces[order[-1]]["outputs"] else ""

        result = {
            "id": run_id,
            "graph_id": graph.get("id"),
            "graph_name": graph.get("name"),
            "status": status,
            "prompt": prompt,
            "output": final,
            "target_score": target,
            "passes": pass_index,
            "latency_seconds": time.monotonic() - started,
            "tokens": sum(t["tokens"] for t in traces.values()),
            "traces": list(traces.values()),
            "graph": graph,
            "overrides": overrides,
            "parent_run_id": ctx.get("parent_run_id"),
        }
        await self._emit({"kind": "GraphFinished", "run_id": run_id, "status": status})
        return result
