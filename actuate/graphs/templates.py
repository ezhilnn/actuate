"""Ready-made graphs. User supplies a prompt; judges gate the final output."""

from __future__ import annotations

from typing import Any

from actuate.graphs.catalog import list_agents


def _n(nid: str, agent: str, x: int, y: int) -> dict[str, Any]:
    meta = next(a for a in list_agents() if a["id"] == agent)
    return {"id": nid, "agent": agent, "x": x, "y": y, "label": meta["title"]}


def _e(eid: str, source: str, target: str) -> dict[str, str]:
    return {"id": eid, "source": source, "target": target}


def _graph(gid: str, name: str, blurb: str, nodes: list, edges: list, *, score: float = 0.85) -> dict[str, Any]:
    return {
        "id": gid,
        "name": name,
        "blurb": blurb,
        "target_score": score,
        "max_passes": 4,
        "nodes": nodes,
        "edges": edges,
    }


def templates() -> list[dict[str, Any]]:
    return [
        _graph(
            "accurate_explainer",
            "Accurate explainer",
            "Research → fact-check → explain → accuracy judge. Public education.",
            [
                _n("in", "ingress", 0, 120),
                _n("r", "researcher", 220, 40),
                _n("f", "fact_checker", 220, 200),
                _n("e", "explainer", 460, 120),
                _n("j", "judge_accuracy", 700, 80),
                _n("c", "judge_clarity", 700, 200),
                _n("out", "egress", 940, 120),
            ],
            [_e("a", "in", "r"), _e("b", "in", "f"), _e("c", "r", "e"), _e("d", "f", "e"),
             _e("e", "e", "j"), _e("f", "e", "c"), _e("g", "j", "out"), _e("h", "c", "out")],
        ),
        _graph(
            "public_health",
            "Public health brief",
            "Health info with safety and completeness judges. Not a diagnosis.",
            [
                _n("in", "ingress", 0, 120),
                _n("m", "medical_info", 220, 40),
                _n("p", "public_health", 220, 200),
                _n("s", "synthesizer", 460, 120),
                _n("js", "judge_safety", 700, 40),
                _n("ja", "judge_accuracy", 700, 200),
                _n("out", "egress", 940, 120),
            ],
            [_e("a", "in", "m"), _e("b", "in", "p"), _e("c", "m", "s"), _e("d", "p", "s"),
             _e("e", "s", "js"), _e("f", "s", "ja"), _e("g", "js", "out"), _e("h", "ja", "out")],
        ),
        _graph(
            "disaster",
            "Disaster communications",
            "Clear alerts: what happened, what to do, what is unknown.",
            [
                _n("in", "ingress", 0, 80),
                _n("d", "disaster_ops", 240, 80),
                _n("h", "humanitarian", 480, 0),
                _n("a", "accessibility", 480, 160),
                _n("j", "judge_clarity", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "d"), _e("b", "d", "h"), _e("c", "d", "a"), _e("d", "h", "j"),
             _e("e", "a", "j"), _e("f", "j", "out")],
        ),
        _graph(
            "misinfo",
            "Civic misinformation check",
            "Separate claim, evidence, and confusion without amplifying lies.",
            [
                _n("in", "ingress", 0, 80),
                _n("m", "misinfo", 220, 80),
                _n("f", "fact_checker", 440, 0),
                _n("c", "civic", 440, 160),
                _n("s", "synthesizer", 660, 80),
                _n("j", "judge_accuracy", 880, 80),
                _n("out", "egress", 1100, 80),
            ],
            [_e("a", "in", "m"), _e("b", "m", "f"), _e("c", "m", "c"), _e("d", "f", "s"),
             _e("e", "c", "s"), _e("f", "s", "j"), _e("g", "j", "out")],
        ),
        _graph(
            "accessible",
            "Accessible rewrite",
            "Inclusion + accessibility + clarity judge.",
            [
                _n("in", "ingress", 0, 80),
                _n("i", "inclusion", 240, 0),
                _n("a", "accessibility", 240, 160),
                _n("e", "editor", 480, 80),
                _n("j", "judge_clarity", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "i"), _e("b", "in", "a"), _e("c", "i", "e"), _e("d", "a", "e"),
             _e("e", "e", "j"), _e("f", "j", "out")],
        ),
        _graph(
            "lesson",
            "Education lesson",
            "Educator + youth-safe editor + completeness.",
            [
                _n("in", "ingress", 0, 80),
                _n("ed", "education", 240, 80),
                _n("y", "youth_safe", 480, 80),
                _n("j", "judge_complete", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "ed"), _e("b", "ed", "y"), _e("c", "y", "j"), _e("d", "j", "out")],
        ),
        _graph(
            "climate",
            "Climate options brief",
            "Climate + policy + ethics + accuracy.",
            [
                _n("in", "ingress", 0, 80),
                _n("cl", "climate", 220, 0),
                _n("po", "policy_brief", 220, 160),
                _n("et", "ethics", 460, 80),
                _n("j", "judge_accuracy", 700, 80),
                _n("out", "egress", 940, 80),
            ],
            [_e("a", "in", "cl"), _e("b", "in", "po"), _e("c", "cl", "et"), _e("d", "po", "et"),
             _e("e", "et", "j"), _e("f", "j", "out")],
        ),
        _graph(
            "grant",
            "Grant narrative",
            "Grant writer + critic + completeness judge.",
            [
                _n("in", "ingress", 0, 80),
                _n("g", "grant", 240, 80),
                _n("k", "critic", 480, 80),
                _n("j", "judge_complete", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "g"), _e("b", "g", "k"), _e("c", "k", "j"), _e("d", "j", "out")],
        ),
        _graph(
            "safety_ethics",
            "Safety and ethics gate",
            "Red team + safety + ethics judges before publish.",
            [
                _n("in", "ingress", 0, 120),
                _n("d", "docs", 220, 120),
                _n("rt", "red_team", 460, 0),
                _n("sf", "safety", 460, 120),
                _n("et", "ethics", 460, 240),
                _n("js", "judge_safety", 700, 120),
                _n("out", "egress", 940, 120),
            ],
            [_e("a", "in", "d"), _e("b", "d", "rt"), _e("c", "d", "sf"), _e("d", "d", "et"),
             _e("e", "rt", "js"), _e("f", "sf", "js"), _e("g", "et", "js"), _e("h", "js", "out")],
        ),
        _graph(
            "translate",
            "Translate and localize",
            "Translator → localizer → clarity judge.",
            [
                _n("in", "ingress", 0, 80),
                _n("t", "translator", 240, 80),
                _n("l", "localizer", 480, 80),
                _n("j", "judge_clarity", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "t"), _e("b", "t", "l"), _e("c", "l", "j"), _e("d", "j", "out")],
        ),
        _graph(
            "research_digest",
            "Research digest",
            "Researcher → citations → summarizer → accuracy.",
            [
                _n("in", "ingress", 0, 80),
                _n("r", "researcher", 220, 80),
                _n("c", "citation", 440, 80),
                _n("s", "summarizer", 660, 80),
                _n("j", "judge_accuracy", 880, 80),
                _n("out", "egress", 1100, 80),
            ],
            [_e("a", "in", "r"), _e("b", "r", "c"), _e("c", "c", "s"), _e("d", "s", "j"), _e("e", "j", "out")],
        ),
        _graph(
            "community_help",
            "Community help map",
            "Resources + inclusion + safety. Verify locally.",
            [
                _n("in", "ingress", 0, 80),
                _n("cm", "community", 240, 0),
                _n("mh", "mental_health", 240, 160),
                _n("i", "inclusion", 480, 80),
                _n("j", "judge_safety", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "cm"), _e("b", "in", "mh"), _e("c", "cm", "i"), _e("d", "mh", "i"),
             _e("e", "i", "j"), _e("f", "j", "out")],
        ),
        _graph(
            "plain_legal",
            "Plain-language rights",
            "Legal explainer + civic + clarity. Not legal advice.",
            [
                _n("in", "ingress", 0, 80),
                _n("l", "legal_plain", 240, 80),
                _n("c", "civic", 480, 80),
                _n("j", "judge_clarity", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "l"), _e("b", "l", "c"), _e("c", "c", "j"), _e("d", "j", "out")],
        ),
        _graph(
            "science",
            "Science for the public",
            "Science comm + fact check + critic + accuracy.",
            [
                _n("in", "ingress", 0, 80),
                _n("sc", "science_comm", 220, 80),
                _n("f", "fact_checker", 440, 0),
                _n("k", "critic", 440, 160),
                _n("s", "synthesizer", 660, 80),
                _n("j", "judge_accuracy", 880, 80),
                _n("out", "egress", 1100, 80),
            ],
            [_e("a", "in", "sc"), _e("b", "sc", "f"), _e("c", "sc", "k"), _e("d", "f", "s"),
             _e("e", "k", "s"), _e("f", "s", "j"), _e("g", "j", "out")],
        ),
        _graph(
            "closed_loop",
            "Classic closed loop",
            "Ingress → researcher → judges → controller → actuator → egress.",
            [
                _n("in", "ingress", 0, 120),
                _n("p", "researcher", 220, 120),
                _n("j", "judge_complete", 440, 40),
                _n("js", "judge_accuracy", 440, 200),
                _n("c", "controller_agent", 660, 120),
                _n("a", "actuator_agent", 880, 120),
                _n("out", "egress", 1100, 120),
            ],
            [_e("a", "in", "p"), _e("b", "p", "j"), _e("c", "p", "js"), _e("d", "j", "c"),
             _e("e", "js", "c"), _e("f", "c", "a"), _e("g", "a", "out")],
        ),
        _graph(
            "data_story",
            "Data story",
            "Analyst + chart spec + explainer + completeness.",
            [
                _n("in", "ingress", 0, 80),
                _n("da", "data_analyst", 240, 0),
                _n("vz", "viz_spec", 240, 160),
                _n("ex", "explainer", 480, 80),
                _n("j", "judge_complete", 720, 80),
                _n("out", "egress", 960, 80),
            ],
            [_e("a", "in", "da"), _e("b", "in", "vz"), _e("c", "da", "ex"), _e("d", "vz", "ex"),
             _e("e", "ex", "j"), _e("f", "j", "out")],
        ),
    ]
