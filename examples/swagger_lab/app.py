"""Sample FastAPI app that consumes the actuate-ai package.

Swagger UI: http://127.0.0.1:8090/docs
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from actuate import Graph, GraphRunner, run_payload, __version__ as ACTUATE_VERSION
from actuate.plants import PROVIDERS, LiteLLMAdapter, StubGenerator

from graphs import custom_ten_lab, mixed_lab

app = FastAPI(
    title="Actuate sample lab",
    description=(
        "Two graph endpoints using `actuate-ai`. "
        "Leave api_base empty unless you use a custom / Ollama host. "
        "Response is `{ pass, final_output }`."
    ),
    version="0.1.0",
)

ProviderId = Literal[
    "nvidia",
    "openai",
    "anthropic",
    "gemini",
    "groq",
    "openrouter",
    "ollama",
    "custom",
    "stub",
]


class RunRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "prompt": "A clinic wants fewer missed appointments. Propose a 30-day plan.",
                    "provider": "stub",
                    "temperature": 0.2,
                    "max_tokens": 80000,
                }
            ]
        }
    )

    prompt: str
    provider: ProviderId = "stub"
    model: str | None = None
    api_key: str | None = Field(default=None, description="LLM key. Leave empty to use env vars.")
    api_base: str | None = Field(
        default=None,
        description="Only for custom/Ollama hosts, e.g. http://localhost:11434/v1. Leave empty for NVIDIA/OpenAI.",
    )
    temperature: float = 0.2
    max_tokens: int = 80_000


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"string", "str", "null", "none", "undefined"}:
        return None
    return text


def _provider_row(provider: str) -> dict[str, Any]:
    for row in PROVIDERS:
        if row["id"] == provider:
            return row
    raise HTTPException(400, f"Unknown provider '{provider}'")


def _plant(body: RunRequest) -> Any:
    row = _provider_row(body.provider)
    if body.provider == "stub":
        return StubGenerator()
    model = _clean(body.model) or (row.get("models") or ["gpt-4o-mini"])[0]
    api_key = _clean(body.api_key) or os.environ.get(str(row.get("env_key") or ""), "") or None
    api_base = _clean(body.api_base)
    if api_base:
        api_base = api_base.rstrip("/")
        if api_base.endswith("/chat/completions"):
            api_base = api_base[: -len("/chat/completions")]
        if not api_base.startswith(("http://", "https://")):
            raise HTTPException(400, "api_base must be a URL like https://host/v1 — leave it empty for NVIDIA/OpenAI.")
    else:
        api_base = row.get("api_base") or None
        if api_base == "":
            api_base = None
    if body.provider not in {"stub", "ollama"} and not api_key:
        raise HTTPException(
            400,
            f"No API key for '{body.provider}'. Paste api_key in the body or set {row.get('env_key')}.",
        )
    return LiteLLMAdapter(
        model=model,
        temperature=body.temperature,
        api_key=api_key,
        api_base=api_base or None,
    )


async def _execute(graph: Graph, body: RunRequest) -> dict[str, Any]:
    try:
        result = await GraphRunner(_plant(body), max_tokens=body.max_tokens).run(graph, prompt=body.prompt)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc
    payload = run_payload(result)
    payload["provider"] = body.provider
    payload["model"] = _clean(body.model)
    payload["graph"] = graph.name
    return payload


@app.get("/health")
def health() -> dict[str, Any]:
    import actuate

    return {
        "status": "ok",
        "package": "actuate-ai",
        "actuate_version": ACTUATE_VERSION,
        "actuate_path": actuate.__file__,
    }


@app.get("/providers")
def providers() -> dict[str, Any]:
    return {
        "providers": [
            {"id": p["id"], "name": p["name"], "models": p.get("models") or []} for p in PROVIDERS
        ]
    }


@app.post("/v1/mixed-graph")
async def mixed_graph(body: RunRequest) -> dict[str, Any]:
    """5 catalog agents (researcher, fact checker, editor, accuracy judge, plus IO) and 3 custom agents."""
    return await _execute(mixed_lab(), body)


@app.post("/v1/custom-graph")
async def custom_graph(body: RunRequest) -> dict[str, Any]:
    """10 custom agents plus ingress/egress. Judge is a custom JSON scorer."""
    return await _execute(custom_ten_lab(), body)
