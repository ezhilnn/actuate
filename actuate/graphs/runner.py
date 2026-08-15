"""Execute a user-designed agent graph until judges pass, budget trips, or passes exhaust.

Ready nodes with no unfinished parents run in parallel (asyncio.gather).
A node that fans out to three children publishes once; those children start together.
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from actuate.domain.protocols import Generator
from actuate.graphs.agent import llm_once, run_specialist
from actuate.graphs.catalog import agent_by_id

LogFn = Callable[[dict[str, Any]], Awaitable[None]]
ProgressFn = Callable[[list[dict[str, Any]]], Awaitable[None]]


class BudgetExceeded(RuntimeError):
    def __init__(self, tokens: int, cap: int) -> None:
        super().__init__(f"Token budget exceeded ({tokens} > {cap})")
        self.tokens = tokens
        self.cap = cap


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


def _children(node_id: str, edges: list[dict[str, str]]) -> list[str]:
    return [e["target"] for e in edges if e["source"] == node_id]


def descendants(start: str, edges: list[dict[str, str]]) -> set[str]:
    found: set[str] = set()
    stack = [start]
    while stack:
        nid = stack.pop()
        if nid in found:
            continue
        found.add(nid)
        stack.extend(_children(nid, edges))
    return found


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


def _title(agent_id: str) -> str:
    try:
        return str(agent_by_id(agent_id)["title"])
    except KeyError:
        return agent_id


class GraphRunner:
    def __init__(
        self,
        generator: Generator,
        *,
        log: LogFn | None = None,
        memory: Any | None = None,
        max_tokens: int = 250_000,
        on_progress: ProgressFn | None = None,
    ) -> None:
        self.generator = generator
        self.log = log
        self.memory = memory
        self.on_progress = on_progress
        self.max_tokens = max(1, int(max_tokens))
        self._tokens_used = 0

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.log:
            await self.log(payload)

    async def _snapshot(self, traces: dict[str, dict[str, Any]]) -> None:
        if self.on_progress:
            await self.on_progress(copy.deepcopy(list(traces.values())))

    def _charge(self, tokens: int) -> None:
        self._tokens_used += int(tokens or 0)
        if self._tokens_used > self.max_tokens:
            raise BudgetExceeded(self._tokens_used, self.max_tokens)

    async def run(
        self,
        graph: dict[str, Any],
        *,
        prompt: str,
        context: dict[str, Any] | None = None,
        run_id: str | None = None,
        overrides: dict[str, str] | None = None,
        prior_traces: dict[str, dict[str, Any]] | None = None,
        rerun_from: str | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or uuid.uuid4().hex
        nodes = {n["id"]: n for n in graph["nodes"]}
        edges = list(graph.get("edges") or [])
        order = topological_order(list(nodes.values()), edges)
        target = float(graph.get("target_score") or 0.85)
        max_passes = int(graph.get("max_passes") or 4)
        freeze = set()
        if rerun_from and rerun_from in nodes:
            freeze = set(nodes) - descendants(rerun_from, edges)
            if prior_traces:
                freeze = {nid for nid in freeze if (prior_traces.get(nid) or {}).get("outputs")}
            else:
                freeze = set()
        traces: dict[str, dict[str, Any]] = {
            nid: {
                "node_id": nid,
                "agent": nodes[nid]["agent"],
                "title": _title(nodes[nid]["agent"]),
                "inputs": [],
                "outputs": [],
                "scores": [],
                "feedback": [],
                "latency_seconds": 0.0,
                "tokens": 0,
                "passes": 0,
                "steps": [],
                "tools": [],
                "frozen": nid in freeze,
            }
            for nid in nodes
        }
        if prior_traces:
            for nid, old in prior_traces.items():
                if nid in traces and nid in freeze:
                    traces[nid]["outputs"] = list(old.get("outputs") or [])
                    traces[nid]["inputs"] = list(old.get("inputs") or [])
                    traces[nid]["scores"] = list(old.get("scores") or [])
                    traces[nid]["feedback"] = list(old.get("feedback") or [])
                    traces[nid]["steps"] = list(old.get("steps") or [])
                    traces[nid]["tokens"] = int(old.get("tokens") or 0)
                    traces[nid]["latency_seconds"] = float(old.get("latency_seconds") or 0)
        ctx = dict(context or {})
        overrides = overrides or {}
        started = time.monotonic()
        status = "exhausted"
        pass_index = 0
        await self._emit(
            {
                "kind": "GraphStarted",
                "run_id": run_id,
                "graph": graph.get("id"),
                "name": graph.get("name"),
                "max_tokens": self.max_tokens,
                "rerun_from": rerun_from,
            }
        )

        def inputs_for(nid: str) -> list[str]:
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

        async def execute(nid: str, pass_index: int) -> None:
            node = nodes[nid]
            spec = agent_by_id(node["agent"])
            title = _title(node["agent"])
            if nid in freeze and traces[nid]["outputs"]:
                await self._emit(
                    {
                        "kind": "NodeSkipped",
                        "run_id": run_id,
                        "node_id": nid,
                        "agent": node["agent"],
                        "title": title,
                        "reason": "frozen from parent run",
                    }
                )
                return

            incoming = inputs_for(nid)
            joined = "\n\n---\n\n".join(incoming)
            traces[nid]["inputs"].append(joined)
            traces[nid]["passes"] = pass_index
            kids = [_title(nodes[c]["agent"]) for c in _children(nid, edges) if c in nodes]
            await self._emit(
                {
                    "kind": "NodeStarted",
                    "run_id": run_id,
                    "node_id": nid,
                    "agent": node["agent"],
                    "title": title,
                    "pass": pass_index,
                    "input": joined[:8000],
                    "fan_out": kids,
                }
            )
            await self._snapshot(traces)

            tool_trail: list[dict[str, Any]] = []
            score: float | None = None
            feedback: str | None = None
            try:
                if spec["kind"] == "io" and spec["id"] == "ingress":
                    text, latency, tokens = prompt, 0.0, 0
                elif spec["kind"] == "io" and spec["id"] == "egress":
                    text, latency, tokens = (incoming[-1] if incoming else prompt), 0.0, 0
                elif spec["kind"] == "judge":
                    judge_prompt = (
                        f"User goal:\n{prompt}\n\nCandidate:\n{incoming[-1] if incoming else ''}\n"
                        f"Target score: {target}"
                    )
                    text, latency, tokens = await llm_once(
                        self.generator, system=spec["system"], prompt=judge_prompt, context=ctx
                    )
                    parsed_score, parsed_fb, passed = _parse_judge(text)
                    score, feedback = parsed_score, parsed_fb
                    traces[nid]["scores"].append(parsed_score)
                    traces[nid]["feedback"].append(parsed_fb)
                    if parsed_score < target or not passed:
                        for parent in _parents(nid, edges):
                            traces[parent]["feedback"].append(parsed_fb)
                else:
                    revision = ""
                    if traces[nid]["feedback"]:
                        revision = "\n\nJudge feedback to address:\n" + traces[nid]["feedback"][-1]
                    user_blob = "\n\n".join(incoming) + revision
                    agent_ctx = {
                        **ctx,
                        "graph": graph,
                        "node_id": nid,
                        "agent": node["agent"],
                        "agent_title": title,
                        "user_goal": prompt,
                        "memory": self.memory,
                    }
                    text, latency, tokens, tool_trail = await run_specialist(
                        self.generator, system=spec["system"], prompt=user_blob, context=agent_ctx
                    )
            except BudgetExceeded:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._emit(
                    {
                        "kind": "NodeFailed",
                        "run_id": run_id,
                        "node_id": nid,
                        "agent": node["agent"],
                        "title": title,
                        "error": str(exc),
                    }
                )
                await self._snapshot(traces)
                raise
            self._charge(tokens)

            traces[nid]["steps"].append(
                {
                    "pass": pass_index,
                    "input": joined,
                    "output": text,
                    "score": score,
                    "feedback": feedback,
                    "latency_seconds": latency,
                    "tokens": tokens,
                    "tools": tool_trail,
                }
            )
            traces[nid]["outputs"].append(text)
            traces[nid]["latency_seconds"] += latency
            traces[nid]["tokens"] += tokens
            traces[nid]["tools"] = list(traces[nid].get("tools") or []) + tool_trail
            await self._emit(
                {
                    "kind": "NodeCompleted",
                    "run_id": run_id,
                    "node_id": nid,
                    "agent": node["agent"],
                    "title": title,
                    "pass": pass_index,
                    "input": joined[:8000],
                    "output": text[:8000],
                    "tokens": tokens,
                    "latency_seconds": round(latency, 4),
                    "tools": [t.get("tool") for t in tool_trail],
                    "delivered_in_parallel_to": kids,
                }
            )
            await self._snapshot(traces)

        try:
            for pass_index in range(1, max_passes + 1):
                remaining = {nid for nid in nodes if nid not in freeze or not traces[nid]["outputs"]}
                if rerun_from:
                    remaining = {nid for nid in remaining if nid not in freeze}
                done_this_pass: set[str] = {nid for nid in freeze if traces[nid]["outputs"]}
                if pass_index == 1:
                    for nid in sorted(freeze):
                        await execute(nid, pass_index)
                while remaining:
                    ready = []
                    for nid in list(remaining):
                        pars = _parents(nid, edges)
                        if all(p in done_this_pass or p not in nodes for p in pars):
                            ready.append(nid)
                    if not ready:
                        raise ValueError("Graph stalled: a node is waiting on an unfinished dependency.")
                    await asyncio.gather(*(execute(nid, pass_index) for nid in ready))
                    done_this_pass.update(ready)
                    remaining -= set(ready)

                judges = [nid for nid in nodes if agent_by_id(nodes[nid]["agent"])["kind"] == "judge"]
                all_ok = True
                for nid in judges:
                    scores = traces[nid]["scores"]
                    if not scores or scores[-1] < target:
                        all_ok = False
                        break
                if all_ok:
                    status = "converged"
                    break
            else:
                status = "exhausted"
        except BudgetExceeded as exc:
            status = "budget_exceeded"
            await self._emit(
                {
                    "kind": "BudgetExceeded",
                    "run_id": run_id,
                    "tokens": exc.tokens,
                    "cap": exc.cap,
                }
            )

        egress_ids = [n["id"] for n in graph["nodes"] if n["agent"] == "egress"]
        final = ""
        if egress_ids and traces[egress_ids[-1]]["outputs"]:
            final = traces[egress_ids[-1]]["outputs"][-1]
        elif order:
            final = traces[order[-1]]["outputs"][-1] if traces[order[-1]]["outputs"] else ""

        judges = [nid for nid in nodes if agent_by_id(nodes[nid]["agent"])["kind"] == "judge"]
        last_scores = {
            nid: traces[nid]["scores"][-1] for nid in judges if traces[nid]["scores"]
        }
        if status == "exhausted":
            scored = ", ".join(f"{_title(nodes[nid]['agent'])}={score:.2f}" for nid, score in last_scores.items()) or "no judge scores"
            stop_reason = (
                f"Stopped after {max_passes} graph passes: judges did not reach target {target:.2f} ({scored})."
            )
        elif status == "converged":
            stop_reason = f"All judges reached target {target:.2f}."
        elif status == "budget_exceeded":
            stop_reason = f"Token budget {self.max_tokens} exceeded."
        else:
            stop_reason = status

        result = {
            "id": run_id,
            "graph_id": graph.get("id"),
            "graph_name": graph.get("name"),
            "status": status,
            "prompt": prompt,
            "output": final,
            "target_score": target,
            "max_passes": max_passes,
            "passes": pass_index,
            "latency_seconds": time.monotonic() - started,
            "tokens": sum(t["tokens"] for t in traces.values()),
            "max_tokens": self.max_tokens,
            "traces": list(traces.values()),
            "graph": graph,
            "overrides": overrides,
            "parent_run_id": ctx.get("parent_run_id"),
            "rerun_from": rerun_from,
            "stop_reason": stop_reason,
            "judge_scores": last_scores,
        }
        await self._emit(
            {
                "kind": "GraphFinished",
                "run_id": run_id,
                "status": status,
                "tokens": result["tokens"],
                "stop_reason": stop_reason,
            }
        )
        await self._snapshot(traces)
        return result
