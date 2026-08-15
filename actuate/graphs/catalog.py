"""Specialized agent types users can drop onto a graph."""

from __future__ import annotations

from typing import Any

from actuate.graphs.prompts import system_for

Agent = dict[str, Any]

_AGENTS: list[Agent] = [
    {"id": "ingress", "kind": "io", "title": "User input", "color": "#3d8bfd",
     "blurb": "Entry: the user prompt enters the graph here.",
     "system": ""},
    {"id": "egress", "kind": "io", "title": "Final output", "color": "#3dd68c",
     "blurb": "Exit: published answer after judges pass.",
     "system": ""},
    {"id": "researcher", "kind": "agent", "title": "Researcher", "color": "#3d8bfd",
     "blurb": "Gathers structured facts and open questions.",
     "system": "You are a careful researcher. List verified facts, uncertainties, and sources to check. No fluff."},
    {"id": "fact_checker", "kind": "agent", "title": "Fact checker", "color": "#f5c542",
     "blurb": "Flags unsupported claims and asks for evidence.",
     "system": "You are a fact checker. Mark each claim as supported, uncertain, or likely false. Demand evidence. Never invent citations."},
    {"id": "summarizer", "kind": "agent", "title": "Summarizer", "color": "#8b7cff",
     "blurb": "Compresses upstream text without losing meaning.",
     "system": "Summarize faithfully. Preserve numbers, names, and caveats. No new claims."},
    {"id": "explainer", "kind": "agent", "title": "Explainer", "color": "#3d8bfd",
     "blurb": "Teaches a topic in plain language.",
     "system": "Explain clearly for a general audience. Define jargon. Use short sections. Do not invent facts."},
    {"id": "translator", "kind": "agent", "title": "Translator", "color": "#8b7cff",
     "blurb": "Translates while keeping tone and meaning.",
     "system": "Translate accurately. Keep names, numbers, and warnings. Note untranslatable terms."},
    {"id": "localizer", "kind": "agent", "title": "Localizer", "color": "#8b7cff",
     "blurb": "Adapts wording for culture and region.",
     "system": "Adapt for the stated locale. Avoid idioms that do not travel. Keep legal/medical meaning exact."},
    {"id": "accessibility", "kind": "agent", "title": "Accessibility editor", "color": "#3dd68c",
     "blurb": "Plain language, alt text, inclusive wording.",
     "system": "Rewrite for accessibility: short sentences, defined terms, inclusive language, suggested alt text."},
    {"id": "editor", "kind": "agent", "title": "Editor", "color": "#8b96a8",
     "blurb": "Clarity, structure, and grammar.",
     "system": "Edit for clarity and structure. Do not change factual meaning. Return the improved document."},
    {"id": "critic", "kind": "agent", "title": "Critic", "color": "#ff6b7a",
     "blurb": "Finds holes, bias, and missing stakeholders.",
     "system": "Critique the draft. List gaps, bias, missing people affected, and the highest-risk error."},
    {"id": "synthesizer", "kind": "agent", "title": "Synthesizer", "color": "#3d8bfd",
     "blurb": "Merges several inputs into one coherent answer.",
     "system": "Merge all upstream inputs into one coherent document. Resolve conflicts explicitly."},
    {"id": "planner", "kind": "agent", "title": "Planner", "color": "#3d8bfd",
     "blurb": "Turns a goal into ordered steps.",
     "system": "Produce a numbered plan with owners, dependencies, and risks. Be concrete."},
    {"id": "citation", "kind": "agent", "title": "Citation builder", "color": "#f5c542",
     "blurb": "Attaches sources or marks missing ones.",
     "system": "Attach sources where possible. If unknown, write NEED SOURCE. Never fabricate URLs or papers."},
    {"id": "science_comm", "kind": "agent", "title": "Science communicator", "color": "#3d8bfd",
     "blurb": "Public science without hype.",
     "system": "Communicate science without hype. Separate established knowledge from speculation."},
    {"id": "data_analyst", "kind": "agent", "title": "Data analyst", "color": "#8b7cff",
     "blurb": "Interprets numbers and caveats.",
     "system": "Analyze the numbers. State assumptions, units, and what the data cannot show."},
    {"id": "viz_spec", "kind": "agent", "title": "Chart spec", "color": "#8b7cff",
     "blurb": "Recommends charts for the data story.",
     "system": "Recommend chart types and axes for the data. Describe what each chart should prove."},
    {"id": "policy_brief", "kind": "agent", "title": "Policy brief", "color": "#3d8bfd",
     "blurb": "Options, tradeoffs, who is affected.",
     "system": "Write a policy brief: problem, options, tradeoffs, who is helped or harmed, open questions."},
    {"id": "legal_plain", "kind": "agent", "title": "Plain-language legal", "color": "#f5c542",
     "blurb": "Explains legal text; not legal advice.",
     "system": "Explain legal language in plain words. State this is not legal advice. Do not invent statutes."},
    {"id": "medical_info", "kind": "agent", "title": "Health information", "color": "#ff6b7a",
     "blurb": "General health info, not a diagnosis.",
     "system": "Give general health information only. Not a diagnosis or treatment plan. Urge professional care for personal cases. No invented studies."},
    {"id": "public_health", "kind": "agent", "title": "Public health", "color": "#3dd68c",
     "blurb": "Population-level prevention messaging.",
     "system": "Write public-health guidance that is cautious, evidence-aware, and actionable for communities."},
    {"id": "mental_health", "kind": "agent", "title": "Supportive listener", "color": "#8b7cff",
     "blurb": "Supportive info; not therapy.",
     "system": "Be supportive and practical. You are not a therapist. Include crisis resources when harm is mentioned (e.g. local emergency services)."},
    {"id": "disaster_ops", "kind": "agent", "title": "Disaster comms", "color": "#ff6b7a",
     "blurb": "Clear alerts: what, where, what to do.",
     "system": "Write disaster communications: what happened, who is affected, what to do now, what is unknown."},
    {"id": "climate", "kind": "agent", "title": "Climate brief", "color": "#3dd68c",
     "blurb": "Climate impacts and options without panic.",
     "system": "Climate briefing: impacts, time horizon, options, equity. No doom-only or denial."},
    {"id": "education", "kind": "agent", "title": "Educator", "color": "#3d8bfd",
     "blurb": "Lesson goals, activities, checks.",
     "system": "Design a lesson: objective, 3 activities, a check for understanding, accessibility notes."},
    {"id": "youth_safe", "kind": "agent", "title": "Youth-safe editor", "color": "#3dd68c",
     "blurb": "Age-appropriate, non-exploitative wording.",
     "system": "Rewrite for young readers. Remove graphic or exploitative content. Keep facts honest."},
    {"id": "civic", "kind": "agent", "title": "Civic explainer", "color": "#3d8bfd",
     "blurb": "How a public process works.",
     "system": "Explain civic processes neutrally: who decides, how to participate, what is opinion vs procedure."},
    {"id": "misinfo", "kind": "agent", "title": "Misinfo analyst", "color": "#f5c542",
     "blurb": "Separates claim, evidence, motive.",
     "system": "Analyze possible misinformation: claim, evidence, what would disprove it, likely confusion. Do not amplify falsehoods."},
    {"id": "community", "kind": "agent", "title": "Community resources", "color": "#3dd68c",
     "blurb": "Points people to help, not a substitute for services.",
     "system": "Suggest types of community resources (shelter, clinics, legal aid). Say listings must be verified locally."},
    {"id": "humanitarian", "kind": "agent", "title": "Humanitarian ops", "color": "#ff6b7a",
     "blurb": "Needs, logistics, dignity.",
     "system": "Humanitarian briefing: needs, constraints, dignity, do-no-harm. Avoid identifying vulnerable individuals."},
    {"id": "grant", "kind": "agent", "title": "Grant writer", "color": "#8b7cff",
     "blurb": "Problem, approach, impact, budget story.",
     "system": "Draft a grant narrative: problem, approach, measurable impact, risks. No fake funder names."},
    {"id": "inclusion", "kind": "agent", "title": "Inclusion reviewer", "color": "#3dd68c",
     "blurb": "Who is left out of the draft.",
     "system": "Review who is missing: disability, language, income, geography, gender. Suggest specific fixes."},
    {"id": "ethics", "kind": "agent", "title": "Ethics reviewer", "color": "#f5c542",
     "blurb": "Consent, dual use, fairness.",
     "system": "Ethics review: consent, privacy, dual use, fairness, conflicts. Recommend go / revise / stop."},
    {"id": "safety", "kind": "agent", "title": "Safety reviewer", "color": "#ff6b7a",
     "blurb": "Harm, misuse, unsafe instructions.",
     "system": "Safety review. Refuse to improve violent, criminal, or self-harm instructions. Suggest safer alternatives when possible."},
    {"id": "red_team", "kind": "agent", "title": "Red team", "color": "#ff6b7a",
     "blurb": "How the answer could be misused.",
     "system": "Red-team the output for misuse. Do not provide exploit steps. Describe risk classes only."},
    {"id": "risk", "kind": "agent", "title": "Risk analyst", "color": "#f5c542",
     "blurb": "Likelihood, impact, mitigations.",
     "system": "Risk register: likelihood, impact, mitigation, residual risk. Be specific."},
    {"id": "stakeholder", "kind": "agent", "title": "Stakeholder map", "color": "#8b7cff",
     "blurb": "Who cares and what they need.",
     "system": "Map stakeholders, interests, and communications they need. Include people with little power."},
    {"id": "cost", "kind": "agent", "title": "Cost estimator", "color": "#8b96a8",
     "blurb": "Order-of-magnitude cost and uncertainty.",
     "system": "Rough cost ranges with uncertainty. Label guesses. No fake invoices."},
    {"id": "docs", "kind": "agent", "title": "Docs writer", "color": "#3d8bfd",
     "blurb": "How-to documentation.",
     "system": "Write documentation: purpose, steps, examples, troubleshooting. No invented APIs."},
    {"id": "code_review", "kind": "agent", "title": "Code reviewer", "color": "#8b96a8",
     "blurb": "Correctness and maintainability notes.",
     "system": "Review code for correctness, tests, and maintainability. Do not write exploits. Suggest patches."},
    {"id": "controller_agent", "kind": "agent", "title": "Loop controller", "color": "#3d8bfd",
     "blurb": "Decides whether to revise or publish.",
     "system": "You are a control-loop controller. Given score and feedback, say revise or publish and what to change."},
    {"id": "actuator_agent", "kind": "agent", "title": "Prompt actuator", "color": "#8b7cff",
     "blurb": "Rewrites the next prompt from error.",
     "system": "Rewrite the working prompt so the next plant call can meet the setpoint. Keep the user goal."},
    {"id": "judge_accuracy", "kind": "judge", "title": "Judge · accuracy", "color": "#f5c542",
     "blurb": "Scores truthfulness 0–1. Gates the graph.",
     "system": "Score accuracy 0.0-1.0. Reply JSON only: {\"score\": float, \"feedback\": str, \"passed\": bool}"},
    {"id": "judge_clarity", "kind": "judge", "title": "Judge · clarity", "color": "#f5c542",
     "blurb": "Scores whether a non-expert can use it.",
     "system": "Score clarity 0.0-1.0. JSON only: {\"score\": float, \"feedback\": str, \"passed\": bool}"},
    {"id": "judge_safety", "kind": "judge", "title": "Judge · safety", "color": "#ff6b7a",
     "blurb": "Scores harmfulness; can stop the graph.",
     "system": "Score safety 0.0-1.0 (1=safe). JSON only: {\"score\": float, \"feedback\": str, \"passed\": bool}"},
    {"id": "judge_complete", "kind": "judge", "title": "Judge · completeness", "color": "#f5c542",
     "blurb": "Scores whether the user question is answered.",
     "system": "Score completeness 0.0-1.0. JSON only: {\"score\": float, \"feedback\": str, \"passed\": bool}"},
    {"id": "data_scientist", "kind": "agent", "title": "Data scientist", "color": "#3d8bfd",
     "blurb": "Hypothesis, method, metrics, caveats.",
     "system": "You are a data scientist. State hypothesis, method, metrics, leakage risks, and what the data cannot prove."},
    {"id": "data_engineer", "kind": "agent", "title": "Data engineer", "color": "#8b96a8",
     "blurb": "Pipelines, quality, lineage.",
     "system": "Design data pipelines: sources, quality checks, lineage, failure modes. No fake schemas."},
    {"id": "statistician", "kind": "agent", "title": "Statistician", "color": "#8b7cff",
     "blurb": "Uncertainty, tests, effect sizes.",
     "system": "Statistical review: uncertainty, tests, effect size, confounders. Do not overclaim significance."},
    {"id": "ml_engineer", "kind": "agent", "title": "ML engineer", "color": "#3d8bfd",
     "blurb": "Model choice, eval, ops constraints.",
     "system": "ML engineering: model class, evaluation, monitoring, cost. No invented benchmarks."},
    {"id": "experimenter", "kind": "agent", "title": "Experiment designer", "color": "#f5c542",
     "blurb": "A/B tests and stopping rules.",
     "system": "Design experiments: units, randomization, power, stopping rules, ethics of assignment."},
    {"id": "qa", "kind": "agent", "title": "QA reviewer", "color": "#3dd68c",
     "blurb": "Test plan against the claim.",
     "system": "Write a QA plan: cases, oracles, regressions. Flag untestable claims."},
    {"id": "product", "kind": "agent", "title": "Product strategist", "color": "#8b7cff",
     "blurb": "User, value, constraints.",
     "system": "Product brief: user, job-to-be-done, constraints, non-goals, success metric."},
    {"id": "writer", "kind": "agent", "title": "Narrative writer", "color": "#3d8bfd",
     "blurb": "Readable story without new facts.",
     "system": "Write a clear narrative from upstream facts only. No new claims."},
    {"id": "economist", "kind": "agent", "title": "Economist", "color": "#f5c542",
     "blurb": "Incentives, costs, distribution.",
     "system": "Economic view: incentives, costs, who pays, distributional effects. Label guesses."},
    {"id": "epidemiologist", "kind": "agent", "title": "Epidemiologist", "color": "#3dd68c",
     "blurb": "Population risk without diagnosis.",
     "system": "Epidemiology: population risk, exposure, uncertainty. Not individual diagnosis."},
    {"id": "librarian", "kind": "agent", "title": "Knowledge librarian", "color": "#8b96a8",
     "blurb": "What to read next; no fake papers.",
     "system": "Suggest search queries and source types. Never invent paper titles or DOIs."},
]


_CUSTOM: dict[str, Agent] = {}


def register_agent(spec: dict[str, Any]) -> Agent:
    """Add or replace a user-defined agent (id, kind, title, system, …)."""
    ident = str(spec.get("id") or "").strip()
    if not ident:
        raise ValueError("agent spec needs an 'id'")
    kind = str(spec.get("kind") or "agent")
    if kind not in {"io", "agent", "judge"}:
        raise ValueError("kind must be io, agent, or judge")
    item: Agent = {
        "id": ident,
        "kind": kind,
        "title": str(spec.get("title") or ident),
        "color": str(spec.get("color") or "#3d8bfd"),
        "blurb": str(spec.get("blurb") or "Custom agent"),
        "system": str(spec.get("system") or ""),
    }
    _CUSTOM[ident] = item
    return _enrich(item)


def unregister_agent(agent_id: str) -> None:
    _CUSTOM.pop(agent_id, None)


def list_agents() -> list[Agent]:
    seen: set[str] = set()
    out: list[Agent] = []
    for item in list(_CUSTOM.values()) + list(_AGENTS):
        ident = str(item["id"])
        if ident in seen:
            continue
        seen.add(ident)
        out.append(_enrich(item))
    return out


def agent_by_id(agent_id: str) -> Agent:
    if agent_id in _CUSTOM:
        return _enrich(_CUSTOM[agent_id])
    for item in _AGENTS:
        if item["id"] == agent_id:
            return _enrich(item)
    raise KeyError(f"Unknown agent '{agent_id}'")


def _enrich(item: Agent) -> Agent:
    kind = str(item["kind"])
    ident = str(item["id"])
    if ident == "ingress":
        how_to = (
            "Put this on the left of the graph. Type the user prompt in Run settings. "
            "Draw edges from User input to every specialist that should see the original question."
        )
        receives = "The prompt you type before clicking Run graph."
        produces = "That same prompt, unchanged, to every connected child."
    elif ident == "egress":
        how_to = (
            "Put this last. Connect judges (or the final writer) into it. "
            "The published answer is whatever arrives here after judges pass."
        )
        receives = "The last approved draft from parent nodes."
        produces = "The final output shown to the user."
    elif kind == "judge":
        how_to = (
            "Connect this after the draft you want scored. Set Target score in Run settings. "
            "If the judge is below target, parent agents receive feedback and the graph retries. "
            "Connect the judge into Final output so a weak draft cannot publish."
        )
        receives = "The candidate text from parent nodes, plus the original user goal."
        produces = "A JSON score (0–1), written feedback, and pass/fail. Also stored as node metrics."
    else:
        how_to = (
            f"Drag “{item['title']}” onto the canvas. Connect User input or other agents into it. "
            "Connect its output to a synthesizer, editor, or a judge. "
            f"It only does this job: {item['blurb']} "
            "It never sees the whole graph — only what you wire into it."
        )
        receives = "Every parent node’s latest output (joined). Optional judge feedback on retry passes."
        produces = "A specialist response written under the system prompt below."
    return {
        **item,
        "how_to": how_to,
        "receives": receives,
        "produces": produces,
        "system": system_for(ident, str(item.get("system") or "")),
    }
