from actuate.graphs.catalog import agent_by_id, list_agents
from actuate.graphs.prompts import SYSTEMS, system_for


def test_every_agent_has_a_long_system_prompt() -> None:
    for agent in list_agents():
        if agent["id"] in {"ingress", "egress"}:
            continue
        text = agent["system"]
        assert len(text) > 1000, agent["id"]
        assert "MISSION" in text or "AXIS:" in text


def test_prompt_catalog_covers_specialists() -> None:
    assert len(SYSTEMS) >= 40
    assert "You are Actuate's Researcher specialist" in system_for("researcher")
    assert agent_by_id("judge_accuracy")["system"].startswith("You are an Actuate quality judge")
