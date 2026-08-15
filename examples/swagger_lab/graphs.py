"""Two demo graphs: mixed catalog+custom, and ten custom specialists."""

from __future__ import annotations

from actuate import Agents, Graph, agent


def mixed_lab() -> Graph:
    clinic = agent(
        "clinic_writer",
        title="Clinic writer",
        system="Write a clinic operations memo. First sentence is the decision. No patient names or IDs.",
    )
    noshow = agent(
        "noshow_analyst",
        title="No-show analyst",
        system="Analyze missed-appointment risk using only the provided fields. State assumptions. No invented statistics.",
    )
    safety = agent(
        "safety_note",
        title="Safety note",
        system="Add a short safety/privacy note: no PHI in outputs, flag medical overclaim. Keep it to 5 lines.",
    )
    return (
        Graph("mixed-lab", target_score=0.75, max_passes=2)
        .add("in", Agents.ingress)
        .add("research", Agents.researcher)
        .add("facts", Agents.fact_checker)
        .add("clinic", clinic)
        .add("noshow", noshow)
        .add("safety", safety)
        .add("editor", Agents.editor)
        .add("judge", Agents.judge_accuracy)
        .add("out", Agents.egress)
        .edge("in", "research")
        .edge("in", "facts")
        .edge("in", "clinic")
        .edge("in", "noshow")
        .edge("research", "editor")
        .edge("facts", "editor")
        .edge("clinic", "editor")
        .edge("noshow", "safety")
        .edge("safety", "editor")
        .connect("editor", "judge", "out")
    )


def custom_ten_lab() -> Graph:
    specs = [
        ("intake_scribe", "Restate the user goal in one sentence and list given facts vs missing facts."),
        ("domain_researcher", "List relevant domain considerations. Mark guesses as NEED SOURCE."),
        ("evidence_auditor", "For each claim, say supported / uncertain / unsupported. No fake citations."),
        ("risk_mapper", "List risks, likelihood (low/med/high), and a mitigation. Be concrete."),
        ("option_generator", "Propose 3 options with tradeoffs. Do not pick a winner yet."),
        ("cost_thinker", "Rough cost and effort for each option. Label guesses."),
        ("equity_reviewer", "Who is helped or harmed, including people with little power."),
        ("memo_writer", "Write the decision memo from upstream notes. First sentence is the question."),
        ("plain_editor", "Tighten the memo. Short sentences. Keep numbers and caveats."),
        (
            "score_judge",
            'Score 0-1 whether the memo answers the goal. JSON only: {"score": float, "feedback": str, "passed": bool}',
        ),
    ]
    g = Graph("custom-ten", target_score=0.7, max_passes=2).add("in", Agents.ingress)
    kinds = {s[0]: ("judge" if s[0] == "score_judge" else "agent") for s in specs}
    for ident, system in specs:
        agent(ident, title=ident.replace("_", " ").title(), system=system, kind=kinds[ident])
        g.add(ident, ident)
    g.add("out", Agents.egress)
    g.edge("in", "intake_scribe")
    fan = [ident for ident, _ in specs if ident not in {"intake_scribe", "memo_writer", "plain_editor", "score_judge"}]
    for ident in fan:
        g.edge("intake_scribe", ident)
        g.edge(ident, "memo_writer")
    g.connect("memo_writer", "plain_editor", "score_judge", "out")
    return g
