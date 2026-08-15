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
