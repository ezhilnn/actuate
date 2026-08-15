<p align="center">
  <img src="docs/logo.png" alt="Actuate" width="96" />
</p>

<h1 align="center">Actuate</h1>

<p align="center">
  <strong>Closed-loop graphs for generation, validation, and reward.</strong><br/>
  Measure. Judge. Correct. Converge. Train.
</p>

<p align="center">
  <a href="https://pypi.org/project/actuate-ai/"><img src="https://img.shields.io/pypi/v/actuate-ai.svg" alt="PyPI" /></a>
  <a href="https://pypi.org/project/actuate-ai/"><img src="https://img.shields.io/pypi/pyversions/actuate-ai.svg" alt="Python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="https://pypi.org/project/actuate-ai/"><img src="https://img.shields.io/pypi/dm/actuate-ai.svg" alt="Downloads" /></a>
  <img src="https://img.shields.io/badge/postgres-production-336791?logo=postgresql&logoColor=white" alt="Postgres" />
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#library">Library</a> ·
  <a href="#training">Training</a> ·
  <a href="#control-console">Console</a> ·
  <a href="#sample-api-swagger">Sample API</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

Actuate wraps any generative **plant** (LLM, NIM, Ollama, custom OpenAI-compatible server) in a **control loop** or a **multi-agent DAG**. Judges score output. The graph retries until a target is met, the token budget trips, or passes exhaust. The same run yields a **reward** your trainer can consume.

```
prompt → agents (parallel DAG) → judges → score / feedback
                                      ↺ until target or stop
                                      ↓
                         reward + traces  →  SFT / DPO / RL
```

| You have | You use |
|---|---|
| A Python service or training job | `pip install actuate-ai` |
| Operators who design graphs | Control console (this repo) |
| A need to try HTTP + Swagger | [`examples/swagger_lab`](examples/swagger_lab) |

## Install

PyPI name is **`actuate-ai`**. The import is **`actuate`**.

```bash
pip install "actuate-ai[plants]"
```

Extras: `plants` (LiteLLM), `persistence` (Postgres), `ui` (FastAPI console), `dev` (pytest).

```python
from actuate import Agents, Graph, GraphRunner, GraphEnv, agent
```

## Library

Build nodes and edges the same way as the designer canvas. Catalog specialists or `agent(..., system="...")` for a custom system prompt.

```python
import asyncio
from actuate import Agents, Graph, GraphRunner, agent
from actuate.plants import LiteLLMAdapter

writer = agent(
    "clinic_writer",
    system="Write a clinic memo. First sentence is the decision. No patient IDs.",
)

graph = (
    Graph("lab", target_score=0.85, max_passes=3)
    .add("in", Agents.ingress)
    .add("writer", writer)
    .add("research", Agents.researcher)
    .add("judge", Agents.judge_accuracy)
    .add("out", Agents.egress)
    .connect("in", "writer")
    .connect("in", "research")
    .edge("writer", "judge")
    .edge("research", "judge")
    .edge("judge", "out")
)

async def main() -> None:
    plant = LiteLLMAdapter(model="meta/llama-3.1-8b-instruct", api_key="nvapi-...")
    result = await GraphRunner(plant, max_tokens=80_000).run(
        graph, prompt="Reduce missed appointments in 30 days."
    )
    print(result["status"], result["reward"], result["output"][:400])

asyncio.run(main())
```

`result["reward"]` is the min judge score (or 1.0 / 0.0 if there is no judge). Node I/O lives in `result["traces"]`. Use `run_payload(result)` for `{ pass, final_output }`.

Ready DAG nodes run in **parallel**. One node can fan out to many children. Frozen ancestors skip work on rerun-from-node.

## Training

Actuate **scores**. Your trainer **updates weights**.

```python
from actuate import GraphEnv, GraphRunner, dpo_pairs

env = GraphEnv(graph, plant, max_tokens=80_000)
row = await env.step("Should we send SMS reminders 48h before visits?")
# row.prompt, row.completion, row.reward, row.feedback

runs = [
    await GraphRunner(plant, max_tokens=80_000).run(graph, prompt=p)
    for p in ("prompt a", "prompt b")
]
pairs = dpo_pairs(runs)  # higher reward = chosen vs rejected
```

See [`examples/train_loop.py`](examples/train_loop.py).

## Control console

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Mission control dashboard" width="900" />
</p>

<p align="center">
  <img src="docs/screenshots/designer.png" alt="Loop / graph designer" width="900" />
</p>

<p align="center">
  <img src="docs/screenshots/graph-testing-1.1.png" alt="22-node graph run" width="900" />
</p>

<p align="center">
  <img src="docs/screenshots/loop-run-1.png" alt="Control loop session" width="900" />
</p>

<p align="center">
  <img src="docs/screenshots/new-run.png" alt="New run" width="900" />
</p>

<p align="center">
  <img src="docs/screenshots/observability.png" alt="Observability" width="900" />
</p>

More live captures (runs, benchmarks, memory, models, plugins, settings, failed vs converged labs) are in [`docs/screenshots`](docs/screenshots).

### Run locally

```powershell
git clone https://github.com/ezhilnn/actuate.git
cd actuate
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://actuate:actuate@localhost:5432/actuate"
$env:ACTUATE_AUTH="0"
pip install -e ".[ui,persistence,plants,dsl,dev]"
python -m actuate.api
```

```powershell
cd ui/frontend
npm install
npm run dev
```

- Console: [http://localhost:5173](http://localhost:5173)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000) · OpenAPI [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Postgres: `localhost:5432`

<p align="center">
  <img src="docs/screenshots/console-api.png" alt="Console FastAPI OpenAPI" width="900" />
</p>

On Windows the API uses a **Selector** event loop so psycopg can talk to Postgres.

Settings → paste `nvapi-…` from [build.nvidia.com](https://build.nvidia.com) (or OpenAI / Anthropic / Gemini / Groq / OpenRouter / custom URL). **New Run → Multi-agent graph**, or **Loop Designer** (drag agents, Ctrl+Z / Ctrl+Y, custom system prompts, Run graph).

| Screen | Role |
|---|---|
| Dashboard | KPIs, activity, templates |
| New Run | Graph (default) or control loop |
| Graph run | Node status, I/O, logs, rerun from node, export pack |
| Loop Designer | DAG authoring + custom agents |
| Runs / Benchmarks | History and compare |
| Memory | Successful trajectories |
| Models / Plugins | Plants, specialists, capability registry |
| Observability | Score, tokens, latency, status mix |
| Settings | Provider keys in Postgres |

Startup **bootstraps** a workspace and demo control systems. Existing API keys are never overwritten.

## Sample API (Swagger)

HTTP lab that **depends on the published package**:

```powershell
pip install -r examples/swagger_lab/requirements.txt
cd examples/swagger_lab
python -m uvicorn app:app --port 8090
```

Open [http://127.0.0.1:8090/docs](http://127.0.0.1:8090/docs).

<p align="center">
  <img src="docs/screenshots/swagger.png" alt="Sample Swagger lab" width="900" />
</p>

| Endpoint | Graph |
|---|---|
| `POST /v1/mixed-graph` | Catalog agents + 3 custom specialists |
| `POST /v1/custom-graph` | 10 custom agents |

```json
{
  "prompt": "A clinic wants fewer missed appointments. 30-day plan.",
  "provider": "nvidia",
  "model": "meta/llama-3.1-8b-instruct",
  "api_key": "nvapi-..."
}
```

Leave `api_base` empty for NVIDIA/OpenAI. Response: `{ "pass": { status, reward, nodes[] }, "final_output": "..." }`.

## Architecture

```
Workspace → ControlSystem → Specification (topology + policy)
                              └── Run (append-only events)
                                    └── GraphRunner / ExecutionEngine
```

The LLM is a **plant**. Quality is a **sensor / judge**. Feedback is **actuation**. Stop conditions are **convergence**, **exhaustion**, **budget**, or **failure** — not “the model finished talking.”

Full write-up: [`docs/architecture/architecture.md`](docs/architecture/architecture.md).

```
actuate/
  domain/        Control system types, signals, events
  engine/        Closed-loop execution
  graphs/        DAG builder, runner, catalog, training, report
  plants/        Stub + LiteLLM (NVIDIA, OpenAI, …)
  persistence/   Postgres store + bootstrap
  api/           Console FastAPI + WebSocket
ui/frontend/     React console
examples/        graph_lab, train_loop, swagger_lab
```

## Models

| Provider | Notes |
|---|---|
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` + `NVIDIA_API_KEY` |
| OpenAI, Anthropic, Gemini, Groq, OpenRouter | LiteLLM + Settings / env |
| Ollama | Local |
| Custom | Your `https://host/v1` + key + model |
| Stub | Tests only (`allow_stub`) |

## Tests

```powershell
pytest tests -q
```

## Contributing

1. `ControlSystem` stays the aggregate root.
2. Events are append-only; signals are immutable.
3. New behavior ships as a **capability**, not a special case in the engine.
4. Production store is **Postgres**.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

---

<p align="center">
  <sub>Traditional AI generates once. Actuate measures, evaluates, corrects, and converges.</sub>
</p>
