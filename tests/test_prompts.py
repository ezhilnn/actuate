from actuate.graphs.catalog import agent_by_id
from actuate.graphs.prompts import SYSTEMS, system_for


def test_every_agent_has_a_long_system_prompt() -> None:
    for agent_id, text in SYSTEMS.items():
        assert len(text) > 280, agent_id
        assert "MISSION" in text or "AXIS:" in text


def test_prompt_catalog_covers_specialists() -> None:
    assert len(SYSTEMS) >= 40
    assert "You are Actuate's Researcher specialist" in system_for("researcher")
    assert agent_by_id("judge_accuracy")["system"].startswith("You are an Actuate quality judge")
