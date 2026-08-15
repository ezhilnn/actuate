import pytest

from actuate import Agents, Graph, GraphEnv, GraphRunner, agent, dpo_pairs, trajectories_from_run
from actuate.graphs.catalog import unregister_agent
from actuate.plants import StubGenerator


def test_node_system_prompt_is_stored() -> None:
    g = Graph("p").add("in", Agents.ingress).add("w", Agents.researcher, system="Only list three facts.")
    assert g.to_dict()["nodes"][1]["system"] == "Only list three facts."
    g = (
        Graph("demo", target_score=0.4, max_passes=1)
        .add("in", Agents.ingress)
        .add("r", Agents.researcher)
        .add("out", Agents.egress)
        .connect("in", "r", "out")
    )
    payload = g.to_dict()
    assert len(payload["nodes"]) == 3
    assert len(payload["edges"]) == 2
    assert payload["nodes"][0]["agent"] == "ingress"


def test_custom_agent_and_cycle_rejected() -> None:
    ident = agent("unit_writer", system="Write one sentence.")
    g = Graph("c").add("a", ident).add("b", Agents.summarizer)
    g.edge("a", "b")
    with pytest.raises(ValueError):
        Graph("bad").add("x", Agents.ingress).add("y", Agents.egress).edge("x", "y").edge("y", "x").to_dict()
    unregister_agent(ident)


@pytest.mark.asyncio
async def test_runner_accepts_graph_and_emits_reward() -> None:
    g = (
        Graph("r", target_score=0.1, max_passes=1)
        .add("in", Agents.ingress)
        .add("r", Agents.researcher)
        .add("out", Agents.egress)
        .connect("in", "r", "out")
    )
    result = await GraphRunner(StubGenerator()).run(g, prompt="reward path")
    assert "reward" in result
    assert result["reward"] >= 0
    rows = trajectories_from_run(result)
    assert rows[0].completion
    assert rows[0].prompt == "reward path"


@pytest.mark.asyncio
async def test_graph_env_collect() -> None:
    g = (
        Graph("e", target_score=0.1, max_passes=1)
        .add("in", Agents.ingress)
        .add("out", Agents.egress)
        .edge("in", "out")
    )
    env = GraphEnv(g, StubGenerator())
    rows = await env.collect(["alpha", "beta"])
    assert len(rows) == 2
    assert rows[0].reward >= 0


def test_dpo_pairs_prefer_higher_reward() -> None:
    pairs = dpo_pairs(
        [
            {"prompt": "q", "output": "good", "reward": 0.9},
            {"prompt": "q", "output": "bad", "reward": 0.2},
        ]
    )
    assert pairs[0]["chosen"] == "good"
    assert pairs[0]["rejected"] == "bad"


def test_sample_graphs_are_dags() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "swagger_lab"))
    from graphs import custom_ten_lab, mixed_lab

    mixed = mixed_lab().to_dict()
    ten = custom_ten_lab().to_dict()
    assert len(mixed["nodes"]) >= 8
    assert len(ten["nodes"]) == 12
    from actuate import run_payload

    fake = {
        "status": "converged",
        "output": "done",
        "reward": 0.9,
        "traces": [{"node_id": "in", "agent": "ingress", "title": "in", "inputs": ["q"], "outputs": ["q"], "scores": [], "feedback": [], "tokens": 0, "latency_seconds": 0, "passes": 1}],
        "graph": mixed,
    }
    payload = run_payload(fake)
    assert "pass" in payload and "final_output" in payload
    assert payload["final_output"] == "done"
