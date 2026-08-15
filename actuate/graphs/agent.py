"""Multi-step agent loop: LLM + tools until a deliverable, or judge JSON."""

from __future__ import annotations

import json
import re
from typing import Any

from actuate.domain.protocols import Generator, MeteredGenerator
from actuate.graphs.tools import run_tool, tool_instructions


def parse_tool_call(text: str) -> dict[str, Any] | None:
    blob = text.strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?", "", blob).removesuffix("```").strip()
    start, end = blob.find("{"), blob.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "tool" not in parsed:
        return None
    args = parsed.get("args") or parsed.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    return {"name": str(parsed["tool"]), "args": args}


async def llm_once(generator: Generator, *, system: str, prompt: str, context: dict[str, Any]) -> tuple[str, float, int]:
    ctx = dict(context)
    if system:
        ctx["system"] = system
    if isinstance(generator, MeteredGenerator):
        outcome = await generator.generate_with_metadata(prompt, context=ctx)
        return outcome.text, outcome.latency_seconds, outcome.prompt_tokens + outcome.completion_tokens
    text = await generator.generate(prompt, context=ctx)
    return text, 0.0, 0


async def run_specialist(
    generator: Generator,
    *,
    system: str,
    prompt: str,
    context: dict[str, Any],
    max_rounds: int = 4,
) -> tuple[str, float, int, list[dict[str, Any]]]:
    """Returns text, latency, tokens, tool trace."""

    tools_note = tool_instructions()
    full_system = f"{system}\n\n{tools_note}" if system else tools_note
    working = prompt
    latency = 0.0
    tokens = 0
    trail: list[dict[str, Any]] = []
    text = ""
    for _ in range(max_rounds):
        text, dt, tok = await llm_once(generator, system=full_system, prompt=working, context=context)
        latency += dt
        tokens += tok
        call = parse_tool_call(text)
        if not call:
            return text, latency, tokens, trail
        result = await run_tool(call["name"], call["args"], context)
        trail.append({"tool": call["name"], "args": call["args"], "result": result[:4000]})
        working = (
            f"{prompt}\n\nPrevious tool call {call['name']} returned:\n{result}\n\n"
            "If you need another tool, emit JSON again. Otherwise write the specialist deliverable now."
        )
    return text, latency, tokens, trail
