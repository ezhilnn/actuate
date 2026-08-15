import json

import pytest

from actuate.graphs.runner import GraphRunner, topological_order
from actuate.graphs.templates import templates
from actuate.plants import StubGenerator


def test_templates_are_dags() -> None:
    for graph in templates():
        order = topological_order(graph["nodes"], graph["edges"])
        assert order
        assert graph["nodes"][0]["agent"] == "ingress"


@pytest.mark.asyncio
async def test_graph_runner_stub_no_judge() -> None:
    graph = {
        "id": "t",
        "name": "t",
        "target_score": 0.5,
        "max_passes": 2,
        "nodes": [
            {"id": "in", "agent": "ingress", "x": 0, "y": 0},
            {"id": "r", "agent": "researcher", "x": 1, "y": 0},
            {"id": "out", "agent": "egress", "x": 2, "y": 0},
        ],
        "edges": [
            {"id": "a", "source": "in", "target": "r"},
            {"id": "b", "source": "r", "target": "out"},
        ],
    }
    result = await GraphRunner(StubGenerator()).run(graph, prompt="Explain clean water access.")
    assert result["status"] == "converged"
    assert result["traces"]
    researcher = next(t for t in result["traces"] if t["agent"] == "researcher")
    assert researcher["outputs"]
    assert researcher["inputs"]


class JsonJudge:
    async def generate(self, prompt: str, *, context: dict) -> str:
        return json.dumps({"score": 0.95, "feedback": "ok", "passed": True})


@pytest.mark.asyncio
async def test_graph_runner_judge_passes() -> None:
    graph = {
        "id": "j",
        "max_passes": 2,
        "target_score": 0.8,
        "nodes": [
            {"id": "in", "agent": "ingress"},
            {"id": "j", "agent": "judge_accuracy"},
            {"id": "out", "agent": "egress"},
        ],
        "edges": [
            {"id": "a", "source": "in", "target": "j"},
            {"id": "b", "source": "j", "target": "out"},
        ],
    }
    result = await GraphRunner(JsonJudge()).run(graph, prompt="hello")
    assert result["status"] == "converged"
    judge = next(t for t in result["traces"] if t["agent"] == "judge_accuracy")
    assert judge["scores"][-1] >= 0.8


@pytest.mark.asyncio
async def test_fan_out_runs_children_in_parallel() -> None:
    graph = {
        "id": "p",
        "max_passes": 1,
        "target_score": 0.1,
        "nodes": [
            {"id": "in", "agent": "ingress"},
            {"id": "a", "agent": "researcher"},
            {"id": "b", "agent": "summarizer"},
            {"id": "out", "agent": "egress"},
        ],
        "edges": [
            {"id": "1", "source": "in", "target": "a"},
            {"id": "2", "source": "in", "target": "b"},
            {"id": "3", "source": "a", "target": "out"},
            {"id": "4", "source": "b", "target": "out"},
        ],
    }
    plant = StubGenerator(delay_seconds=0.2)
    started = __import__("time").monotonic()
    result = await GraphRunner(plant).run(graph, prompt="parallel")
    elapsed = __import__("time").monotonic() - started
    assert result["status"] == "converged"
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_token_budget_hard_stop() -> None:
    graph = {
        "id": "b",
        "max_passes": 1,
        "nodes": [
            {"id": "in", "agent": "ingress"},
            {"id": "r", "agent": "researcher"},
            {"id": "out", "agent": "egress"},
        ],
        "edges": [{"id": "a", "source": "in", "target": "r"}, {"id": "b", "source": "r", "target": "out"}],
    }
    result = await GraphRunner(StubGenerator(), max_tokens=2).run(graph, prompt="budget please stop")
    assert result["status"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_rerun_from_node_freezes_ancestors() -> None:
    graph = {
        "id": "r",
        "max_passes": 1,
        "nodes": [
            {"id": "in", "agent": "ingress"},
            {"id": "r", "agent": "researcher"},
            {"id": "s", "agent": "summarizer"},
            {"id": "out", "agent": "egress"},
        ],
        "edges": [
            {"id": "a", "source": "in", "target": "r"},
            {"id": "b", "source": "r", "target": "s"},
            {"id": "c", "source": "s", "target": "out"},
        ],
    }
    first = await GraphRunner(StubGenerator()).run(graph, prompt="original")
    prior = {t["node_id"]: t for t in first["traces"]}
    logs: list[str] = []

    async def log(p: dict) -> None:
        logs.append(p["kind"])

    second = await GraphRunner(StubGenerator(), log=log).run(
        graph,
        prompt="original",
        prior_traces=prior,
        rerun_from="s",
        overrides={"s": "edited input for summarizer"},
    )
    assert "NodeSkipped" in logs
    summarizer = next(t for t in second["traces"] if t["agent"] == "summarizer")
    assert "edited input" in summarizer["inputs"][-1]
