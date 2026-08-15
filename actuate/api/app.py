"""FastAPI control-console backend."""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from actuate.runtime_loop import configure_windows_selector_loop

configure_windows_selector_loop()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from actuate.domain.capability import CapabilityKinds
from actuate.domain.control_system import ControlSystem, Workspace
from actuate.domain.events import Event, EventLog, RunStarted
from actuate.domain.policy import (
    ActuationPolicy,
    ConvergenceCriteria,
    LoopPolicy,
    RetryStrategyName,
    SetPoint,
    StabilityGuard,
)
from actuate.domain.run import (
    Run,
    convergence_progress,
    current_status,
    ended_at,
    failure_reason,
    iterations,
    metrics,
    started_at,
)
from actuate.domain.specification import Specification, create_specification
from actuate.domain.templates import standard_closed_loop
from actuate.engine.execution_engine import ExecutionEngine
from actuate.engine.graph import topology_as_dict
from actuate.graphs import GraphRunner, list_agents, templates as graph_templates
from actuate.memory import InMemoryVectorStore, LearningGraph
from actuate.persistence.in_memory_store import InMemoryRunStore
from actuate.plants import PROVIDERS
from actuate.plugins import register_builtins
from actuate.telemetry.persistence_sink import PersistenceEventSink

ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "custom": "CUSTOM_API_KEY",
}

DEFAULT_API_BASES = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "ollama": "http://localhost:11434",
}


class Hub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    async def join(self, run_id: str, websocket: WebSocket) -> None:
        self._rooms.setdefault(run_id, set()).add(websocket)

    def leave(self, run_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(run_id)
        if room is not None:
            room.discard(websocket)

    async def publish(self, run_id: str, payload: dict[str, Any]) -> None:
        for websocket in list(self._rooms.get(run_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001
                self.leave(run_id, websocket)


class WebSocketSink:
    def __init__(self, hub: Hub) -> None:
        self.hub = hub

    async def handle(self, event: Event) -> None:
        payload = {
            "id": event.id,
            "run_id": event.run_id,
            "at": event.at,
            "kind": type(event).__name__,
            "data": _event_view(event),
        }
        await self.hub.publish(event.run_id, payload)


def _event_view(event: Event) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for name in getattr(event, "__dataclass_fields__", {}):
        if name in {"id", "run_id", "at"}:
            continue
        value = getattr(event, name)
        if hasattr(value, "__dataclass_fields__"):
            data[name] = {
                key: getattr(value, key)
                for key in value.__dataclass_fields__
                if key not in {"metadata"}
                and not callable(getattr(value, key))
                and not isinstance(getattr(value, key), type)
            }
            data[name]["kind"] = type(value).__name__
            for key, item in list(data[name].items()):
                if isinstance(item, tuple):
                    data[name][key] = list(item)
                if hasattr(item, "__dataclass_fields__"):
                    data[name][key] = str(item)
        else:
            data[name] = value
    return data


class AppState:
    def __init__(self) -> None:
        self.store: Any = InMemoryRunStore()
        self.registry = register_builtins()
        self.hub = Hub()
        self.workspace = Workspace(name="default")
        self.running: dict[str, asyncio.Task[Run]] = {}
        self.vectors = InMemoryVectorStore()
        self.memory = LearningGraph(self.vectors)
        self.designer: dict[str, Any] = {
            "provider": "nvidia",
            "model": "meta/llama-3.1-8b-instruct",
            "sensor": "rule",
            "actuator": "prompt",
            "controller": "rule",
            "prompt": "Design a PID-style controller for an LLM plant. Be specific.",
            "api_base": "https://integrate.api.nvidia.com/v1",
        }
        self.graphs: dict[str, dict[str, Any]] = {}
        self.graph_runs: dict[str, dict[str, Any]] = {}
        self.graph_logs: dict[str, list[dict[str, Any]]] = {}


STATE = AppState()


async def _init_store() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        from actuate.persistence.sql_store import SqlRunStore

        store = SqlRunStore(url)
        await store.create_schema()
        STATE.store = store
    from actuate.persistence.bootstrap import seed_store

    STATE.workspace = await seed_store(STATE.store)
    keys = await STATE.store.get_keys()
    for provider, key in keys.items():
        if provider.endswith("_base"):
            continue
        env_name = ENV_MAP.get(provider)
        if env_name and key:
            os.environ[env_name] = key
            if provider == "nvidia":
                os.environ["NVIDIA_NIM_API_KEY"] = key
    if hasattr(STATE.store, "list_graph_runs"):
        for row in await STATE.store.list_graph_runs():
            if row.get("id"):
                STATE.graph_runs[row["id"]] = row


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    await _init_store()
    yield


app = FastAPI(title="Actuate", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewControlSystem(BaseModel):
    name: str
    description: str = ""


class NewRunRequest(BaseModel):
    prompt: str
    model: str = "meta/llama-3.1-8b-instruct"
    provider: str = "nvidia"
    temperature: float = 0.2
    max_iterations: int = 8
    target_score: float = Field(default=0.95, ge=0.0, le=1.0)
    gain: float = Field(default=0.5, ge=0.0, le=1.0)
    retry_strategy: str = "exponential"
    sensor: str = "rule"
    actuator: str = "prompt"
    controller: str = "rule"
    required_phrases: list[str] = Field(default_factory=list)
    min_length: int = 80
    min_iterations: int = 3
    name: str = "Untitled loop"
    control_system_id: str | None = None
    control_system_name: str = "adhoc"
    api_base: str | None = None
    api_key: str | None = None
    allow_stub: bool = False


class KeyPayload(BaseModel):
    provider: str
    api_key: str
    api_base: str | None = None


class DesignerPayload(BaseModel):
    provider: str = "nvidia"
    model: str = "meta/llama-3.1-8b-instruct"
    sensor: str = "rule"
    actuator: str = "prompt"
    controller: str = "rule"
    prompt: str = ""
    api_base: str | None = None


class GraphRunRequest(BaseModel):
    prompt: str
    graph: dict[str, Any]
    provider: str = "nvidia"
    model: str = "meta/llama-3.1-8b-instruct"
    temperature: float = 0.2
    api_base: str | None = None
    api_key: str | None = None
    allow_stub: bool = False
    name: str = "Untitled graph"
    node_overrides: dict[str, str] = Field(default_factory=dict)
    parent_run_id: str | None = None


class SavedGraph(BaseModel):
    id: str | None = None
    name: str = "untitled"
    graph: dict[str, Any]


def _run_summary(run: Run) -> dict[str, Any]:
    summary = metrics(run)
    return {
        "id": run.id,
        "specification_id": run.specification_id,
        "status": current_status(run),
        "started_at": started_at(run),
        "ended_at": ended_at(run),
        "failure": failure_reason(run),
        "convergence": convergence_progress(run),
        "iterations": summary.iteration_count,
        "latency_seconds": summary.total_latency_seconds,
        "tokens": summary.total_tokens,
        "best_score": summary.best_score,
        "kind": "loop",
        "name": None,
    }


def _iteration_view(run: Run) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view in iterations(run):
        rows.append(
            {
                "index": view.index,
                "prompt": view.prompt.text if view.prompt else None,
                "output": view.output.text if view.output else None,
                "score": view.error_signal.measured if view.error_signal else None,
                "error": view.error_signal.error if view.error_signal else None,
                "feedback": [obs.feedback for obs in view.observations],
                "correction": view.control_signal.revised_prompt if view.control_signal else None,
                "latency_seconds": view.output.latency_seconds if view.output else None,
                "tokens": view.output.usage.total_tokens if view.output else 0,
            }
        )
    return rows


async def _load_run(run_id: str) -> Run:
    events = await STATE.store.load_events(run_id)
    spec_id = ""
    starts = [e for e in events if isinstance(e, RunStarted)]
    if starts:
        spec_id = starts[0].specification_id
    return Run(id=run_id, specification_id=spec_id, events=EventLog(events))


@app.get("/api/health")
async def health() -> dict[str, Any]:
    backend = "postgres" if os.environ.get("DATABASE_URL") else "memory"
    keys = await STATE.store.get_keys()
    live = []
    for item in PROVIDERS:
        if item["id"] in {"stub"}:
            continue
        env_key = item.get("env_key")
        if keys.get(item["id"]) or (env_key and os.environ.get(str(env_key))):
            live.append(item["id"])
    return {
        "status": "ok",
        "persistence": backend,
        "bootstrapped": True,
        "mode": "llm-only",
        "plant": "llm" if live else "disconnected",
        "llm_connected": bool(live),
        "configured_providers": live,
        "hint": None
        if live
        else "Save an NVIDIA / OpenAI / custom OpenAI-compatible key in Settings. Stub/mock plants are disabled.",
    }


@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    keys = await STATE.store.get_keys()
    providers = []
    for item in PROVIDERS:
        if item["id"] == "stub":
            continue
        env_key = item["env_key"]
        if item["id"] == "ollama":
            configured = bool(keys.get("ollama") or os.environ.get("OLLAMA_API_BASE"))
        elif env_key is None:
            configured = False
        else:
            configured = bool(keys.get(item["id"]) or os.environ.get(str(env_key)))
        stored_base = keys.get(f"{item['id']}_base") or item.get("api_base") or ""
        providers.append(
            {
                **item,
                "configured": configured,
                "default": item["models"][0],
                "api_base": stored_base,
            }
        )
    return {"providers": providers}


@app.get("/api/capabilities")
async def list_capabilities() -> dict[str, Any]:
    descriptors = STATE.registry.list_descriptors()
    return {
        "capabilities": [
            {
                "kind": d.kind,
                "name": d.name,
                "version": d.version,
                "author": d.author,
                "description": d.description,
                "config_schema": d.config_schema,
                "compatible_with": list(d.compatible_with),
            }
            for d in descriptors
            if not (d.kind == CapabilityKinds.PLANT and d.name == "stub")
        ]
    }


@app.get("/api/workspaces")
async def workspaces() -> dict[str, Any]:
    rows = await STATE.store.list_workspaces()
    return {"workspaces": [{"id": w.id, "name": w.name, "created_at": w.created_at} for w in rows]}


@app.post("/api/control-systems")
async def create_control_system(body: NewControlSystem) -> dict[str, str]:
    system = ControlSystem(
        workspace_id=STATE.workspace.id,
        name=body.name,
        description=body.description,
    )
    await STATE.store.save_control_system(system)
    return {"id": system.id, "name": system.name}


@app.get("/api/control-systems")
async def list_control_systems() -> dict[str, Any]:
    rows = await STATE.store.list_control_systems()
    return {
        "control_systems": [
            {"id": s.id, "name": s.name, "description": s.description, "workspace_id": s.workspace_id}
            for s in rows
        ]
    }


async def _credentials(provider: str, api_key: str | None, api_base: str | None) -> tuple[str | None, str | None]:
    keys = await STATE.store.get_keys()
    env_name = ENV_MAP.get(provider, "")
    resolved_key = api_key or keys.get(provider) or (os.environ.get(env_name) if env_name else None)
    resolved_base = api_base or keys.get(f"{provider}_base") or DEFAULT_API_BASES.get(provider)
    if provider == "ollama":
        resolved_base = resolved_base or os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    return resolved_key or None, resolved_base


def _plant_for(
    provider: str,
    model: str,
    temperature: float,
    *,
    api_key: str | None,
    api_base: str | None,
) -> tuple[str, dict[str, Any]]:
    if provider == "stub" or model.startswith("stub/"):
        return "stub", {}
    params: dict[str, Any] = {"model": model, "temperature": temperature}
    if api_base:
        params["api_base"] = api_base
    if api_key:
        params["api_key"] = api_key
    return "litellm", params


def _generator(plant_name: str, params: dict[str, Any]) -> Any:
    from actuate.plants import LiteLLMAdapter, StubGenerator

    if plant_name == "stub":
        return StubGenerator()
    return LiteLLMAdapter(**params)


@app.get("/api/agents")
async def agents() -> dict[str, Any]:
    return {"agents": list_agents()}


@app.get("/api/graph-templates")
async def list_graph_templates() -> dict[str, Any]:
    return {"templates": graph_templates()}


@app.post("/api/graphs")
async def save_graph(body: SavedGraph) -> dict[str, str]:
    gid = body.id or uuid.uuid4().hex
    STATE.graphs[gid] = {"id": gid, "name": body.name, **body.graph}
    return {"id": gid}


@app.get("/api/graphs")
async def list_graphs() -> dict[str, Any]:
    return {"graphs": [{"id": g["id"], "name": g.get("name", g["id"])} for g in STATE.graphs.values()]}


@app.get("/api/graphs/{graph_id}")
async def get_graph(graph_id: str) -> dict[str, Any]:
    if graph_id not in STATE.graphs:
        raise HTTPException(404, "unknown graph")
    return STATE.graphs[graph_id]


@app.post("/api/graphs/run")
async def start_graph_run(body: GraphRunRequest) -> dict[str, str]:
    if body.provider == "stub" and not body.allow_stub:
        raise HTTPException(400, "Stub/mock plant is disabled. Configure a real LLM in Settings.")
    api_key, api_base = await _credentials(body.provider, body.api_key, body.api_base)
    if body.provider not in {"stub", "ollama"} and not api_key:
        raise HTTPException(400, f"No API key configured for '{body.provider}'.")
    plant_name, plant_params = _plant_for(
        body.provider, body.model, body.temperature, api_key=api_key, api_base=api_base
    )
    generator = _generator(plant_name, plant_params)
    run_id = uuid.uuid4().hex
    display = body.name or body.graph.get("name") or "Untitled graph"
    body.graph = {**body.graph, "name": display}
    STATE.graph_runs[run_id] = {
        "id": run_id,
        "status": "running",
        "name": display,
        "prompt": body.prompt,
        "graph": body.graph,
        "traces": [],
        "logs": [],
        "output": "",
        "provider": body.provider,
        "model": body.model,
        "plant": "llm" if body.provider != "stub" else "stub",
        "parent_run_id": body.parent_run_id,
        "kind": "graph",
    }
    STATE.graph_logs[run_id] = []
    if hasattr(STATE.store, "save_graph_run"):
        await STATE.store.save_graph_run(STATE.graph_runs[run_id])

    async def _log(payload: dict[str, Any]) -> None:
        STATE.graph_logs[run_id].append(payload)
        STATE.graph_runs[run_id].setdefault("logs", []).append(payload)
        await STATE.hub.publish(run_id, payload)

    async def _go() -> None:
        try:
            result = await GraphRunner(generator, log=_log).run(
                body.graph,
                prompt=body.prompt,
                run_id=run_id,
                overrides=body.node_overrides,
                context={"parent_run_id": body.parent_run_id},
            )
            STATE.graph_runs[run_id].update(result)
            STATE.graph_runs[run_id]["name"] = display
            STATE.graph_runs[run_id]["plant"] = "llm" if body.provider != "stub" else "stub"
            STATE.graph_runs[run_id]["provider"] = body.provider
            STATE.graph_runs[run_id]["model"] = body.model
            STATE.graph_runs[run_id]["kind"] = "graph"
            if hasattr(STATE.store, "save_graph_run"):
                await STATE.store.save_graph_run(STATE.graph_runs[run_id])
        except Exception as exc:  # noqa: BLE001
            STATE.graph_runs[run_id]["status"] = "failed"
            STATE.graph_runs[run_id]["output"] = str(exc)
            if hasattr(STATE.store, "save_graph_run"):
                await STATE.store.save_graph_run(STATE.graph_runs[run_id])
            await _log({"kind": "GraphFailed", "run_id": run_id, "error": str(exc)})

    STATE.running[run_id] = asyncio.create_task(_go())
    return {"run_id": run_id}


@app.get("/api/graph-runs")
async def list_graph_runs() -> dict[str, Any]:
    stored = await STATE.store.list_graph_runs() if hasattr(STATE.store, "list_graph_runs") else []
    by_id = {row.get("id"): row for row in stored if row.get("id")}
    by_id.update(STATE.graph_runs)
    rows = []
    for item in by_id.values():
        rows.append(
            {
                "id": item.get("id"),
                "kind": "graph",
                "name": item.get("name") or item.get("graph_name") or "Graph run",
                "status": item.get("status"),
                "graph_name": item.get("graph_name") or (item.get("graph") or {}).get("name"),
                "tokens": item.get("tokens", 0),
                "latency_seconds": item.get("latency_seconds", 0),
                "passes": item.get("passes", 0),
                "prompt": (item.get("prompt") or "")[:240],
            }
        )
    return {"runs": list(reversed(list(rows)))}


@app.get("/api/graph-runs/{run_id}")
async def get_graph_run(run_id: str) -> dict[str, Any]:
    if run_id in STATE.graph_runs:
        return STATE.graph_runs[run_id]
    loaded = await STATE.store.load_graph_run(run_id) if hasattr(STATE.store, "load_graph_run") else None
    if not loaded:
        raise HTTPException(404, "unknown graph run")
    return loaded


@app.get("/api/activity")
async def activity() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for run_id in await STATE.store.list_run_ids():
        run = await _load_run(run_id)
        row = _run_summary(run)
        name = "Loop run"
        prompt = ""
        try:
            spec = await STATE.store.load_specification(run.specification_id)
            name = spec.metadata.get("name") or name
            prompt = spec.metadata.get("prompt") or ""
            row["provider"] = spec.metadata.get("provider")
            row["model"] = spec.metadata.get("model")
        except Exception:  # noqa: BLE001
            pass
        row.update({"kind": "loop", "name": name, "prompt": prompt[:240], "href": f"/live/{run_id}"})
        items.append(row)
    graphs = (await list_graph_runs())["runs"]
    for g in graphs:
        items.append({**g, "href": f"/graph/{g['id']}", "iterations": g.get("passes") or 0, "best_score": None})
    items.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
    return {"runs": items}


@app.post("/api/runs")
async def start_run(body: NewRunRequest) -> dict[str, str]:
    if body.provider == "stub" and not body.allow_stub:
        raise HTTPException(
            400,
            "Stub/mock plant is disabled. Save a real LLM key in Settings "
            "(NVIDIA, OpenAI, Anthropic, Gemini, Groq, OpenRouter, or a custom OpenAI-compatible URL).",
        )
    api_key, api_base = await _credentials(body.provider, body.api_key, body.api_base)
    if body.provider not in {"stub", "ollama"} and not api_key:
        raise HTTPException(
            400,
            f"No API key configured for '{body.provider}'. Open Settings, save the key, then start the run.",
        )

    if body.control_system_id:
        system_id = body.control_system_id
    else:
        system = ControlSystem(workspace_id=STATE.workspace.id, name=body.control_system_name)
        await STATE.store.save_control_system(system)
        system_id = system.id

    plant_name, plant_params = _plant_for(
        body.provider, body.model, body.temperature, api_key=api_key, api_base=api_base
    )
    sensor_params: dict[str, Any] = {"min_length": body.min_length}
    if body.required_phrases:
        sensor_params["required_phrases"] = body.required_phrases
    topology = standard_closed_loop(
        plant_name=plant_name,
        plant_params=plant_params,
        sensor_name=body.sensor,
        sensor_params=sensor_params,
        actuator_name=body.actuator,
        controller_name=body.controller,
    )
    try:
        retry = RetryStrategyName(body.retry_strategy)
    except ValueError:
        retry = RetryStrategyName.EXPONENTIAL
    spec = create_specification(
        control_system_id=system_id,
        version_number=1,
        topology=topology,
        policies=LoopPolicy(
            set_point=SetPoint(target=body.target_score),
            convergence=ConvergenceCriteria(),
            stability=StabilityGuard(max_iterations=body.max_iterations, min_iterations=body.min_iterations),
            actuation=ActuationPolicy(gain=body.gain, retry_strategy=retry),
        ),
        metadata={
            "prompt": body.prompt,
            "model": body.model,
            "provider": body.provider,
            "plant": "llm" if body.provider != "stub" else "stub",
            "api_base": api_base or "",
            "name": body.name,
            "kind": "loop",
        },
    )
    await STATE.store.save_specification(spec)
    run_id = uuid.uuid4().hex
    engine = ExecutionEngine(
        memory=STATE.memory,
        event_sinks=[PersistenceEventSink(STATE.store), WebSocketSink(STATE.hub)],
    )

    async def _go() -> Run:
        run = await engine.run(
            spec, registry=STATE.registry, initial_prompt=body.prompt, run_id=run_id
        )
        await _index_memory(run)
        return run

    STATE.running[run_id] = asyncio.create_task(_go())
    return {"run_id": run_id, "specification_id": spec.id}


@app.get("/api/runs")
async def list_runs() -> dict[str, Any]:
    ids = await STATE.store.list_run_ids()
    summaries = []
    for run_id in ids:
        run = await _load_run(run_id)
        summaries.append(_run_summary(run))
    summaries.sort(key=lambda row: row.get("started_at") or 0, reverse=True)
    return {"runs": summaries}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    try:
        run = await _load_run(run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, f"unknown run {run_id}") from exc
    graph = None
    spec_meta: dict[str, Any] = {}
    try:
        spec: Specification = await STATE.store.load_specification(run.specification_id)
        graph = topology_as_dict(spec.topology)
        spec_meta = spec.metadata
    except Exception:  # noqa: BLE001
        spec_meta = {}
        graph = None
    return {
        **_run_summary(run),
        "metadata": spec_meta,
        "graph": graph,
        "iterations": _iteration_view(run),
        "events": [
            {"id": e.id, "at": e.at, "kind": type(e).__name__, "data": _event_view(e)}
            for e in run.events
        ],
    }


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    ids = await STATE.store.list_run_ids()
    runs = [await _load_run(run_id) for run_id in ids]
    summaries = [_run_summary(run) for run in runs]
    running = sum(1 for row in summaries if row["status"] == "running")
    finished = [row for row in summaries if row["status"] not in {"running", "pending"}]
    success = [row for row in finished if row["status"] == "converged"]
    scores = [row["best_score"] for row in summaries if row["best_score"] is not None]
    return {
        "kpis": {
            "running": running,
            "success_rate": (len(success) / len(finished)) if finished else 0.0,
            "average_quality": (sum(scores) / len(scores)) if scores else 0.0,
            "average_iterations": (
                sum(row["iterations"] for row in summaries) / len(summaries) if summaries else 0.0
            ),
            "latency": (
                sum(row["latency_seconds"] for row in summaries) / len(summaries) if summaries else 0.0
            ),
            "tokens": sum(row["tokens"] for row in summaries),
            "cost": 0.0,
        },
        "recent_runs": sorted(summaries, key=lambda row: row.get("started_at") or 0, reverse=True)[:8],
        "recent_events": [],
    }


@app.get("/api/memory")
async def memory() -> dict[str, Any]:
    rows = STATE.vectors.rows()
    return {
        "count": len(rows),
        "records": [
            {
                "text": record.text,
                "score": record.score,
                "kind": record.kind,
                "metadata": record.metadata,
            }
            for record, _emb in rows
        ],
    }


async def _index_memory(run: Run) -> None:
    from actuate.domain.run import current_status, iterations

    if current_status(run) != "converged":
        return
    views = iterations(run)
    if not views or views[0].prompt is None or views[-1].output is None:
        return
    score = views[-1].error_signal.measured if views[-1].error_signal else 0.0
    await STATE.memory.record_success(
        prompt=views[0].prompt.text,
        revision=views[-1].output.text,
        score=score,
    )


@app.get("/api/designer")
async def get_designer() -> dict[str, Any]:
    return STATE.designer


@app.put("/api/designer")
async def put_designer(body: DesignerPayload) -> dict[str, Any]:
    STATE.designer.update(body.model_dump())
    return STATE.designer


@app.get("/api/keys")
async def key_status() -> dict[str, Any]:
    keys = await STATE.store.get_keys()
    return {
        "configured": {
            provider: bool(keys.get(provider) or os.environ.get(env_name, ""))
            for provider, env_name in ENV_MAP.items()
        }
    }


@app.post("/api/keys")
async def put_key(body: KeyPayload) -> dict[str, str]:
    await STATE.store.put_key(body.provider, body.api_key)
    if body.api_base:
        await STATE.store.put_key(f"{body.provider}_base", body.api_base)
    env_name = ENV_MAP.get(body.provider)
    if env_name:
        os.environ[env_name] = body.api_key
    if body.provider == "nvidia":
        os.environ["NVIDIA_NIM_API_KEY"] = body.api_key
    return {"status": "saved", "provider": body.provider}


@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    await STATE.hub.join(run_id, websocket)
    try:
        run = await _load_run(run_id)
        for event in run.events:
            await websocket.send_json(
                {
                    "id": event.id,
                    "run_id": event.run_id,
                    "at": event.at,
                    "kind": type(event).__name__,
                    "data": _event_view(event),
                }
            )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        STATE.hub.leave(run_id, websocket)
    except Exception:
        STATE.hub.leave(run_id, websocket)


def run() -> None:
    import asyncio

    from uvicorn import Config, Server

    from actuate.runtime_loop import selector_loop_factory

    configure_windows_selector_loop()
    config = Config("actuate.api.app:app", host="0.0.0.0", port=8000, reload=False)
    server = Server(config)
    asyncio.run(server.serve(), loop_factory=selector_loop_factory())


from pathlib import Path

_DIST = Path(__file__).resolve().parents[2] / "ui" / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
