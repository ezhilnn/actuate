# Actuate

<p align="center">
  <strong>Closed-loop feedback control for AI systems</strong><br/>
  Measure. Correct. Converge. Repeat.
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/architecture-control%20systems-7c5cff" alt="Architecture" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/postgres-required%20(prod)-336791?logo=postgresql&logoColor=white" alt="Postgres" /></a>
  <a href="https://github.com/actuate-ai/actuate/stargazers"><img src="https://img.shields.io/github/stars/actuate-ai/actuate?style=social" alt="Stars" /></a>
  <a href="https://github.com/actuate-ai/actuate/network/members"><img src="https://img.shields.io/github/forks/actuate-ai/actuate?style=social" alt="Forks" /></a>
</p>

<p align="center">
  <a href="#why-actuate">Why</a> ·
  <a href="#the-idea">Idea</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#control-console">Console</a> ·
  <a href="#star-fork-clone">Star / Fork / Clone</a>
</p>

---

Actuate is **not** an LLM orchestration framework, a graph workflow engine, or a chatbot.

It is an engineering framework for building **closed-loop feedback control systems** around any generative plant (an LLM today; a VLM, API, or physical actuator tomorrow). A user designs a **control system**. That system may contain a feedback loop. The loop is a control strategy — it is not the product.

Traditional AI:

```
prompt → model → response
```

Actuate:

```
setpoint → plant → sensor → error → controller → actuator ↺ plant
                         until convergence
```

The LLM is a **plant**. Quality is a **measured signal**. The difference from target quality is an **error signal**. Prompt or policy updates are **actuation**. Stopping is **convergence**, **exhaustion**, **oscillation**, or **timeout** — not “the model finished talking.”

## Why Actuate

| Typical stack | Actuate |
|---|---|
| Generate once and hope | Iterate until a measurable setpoint is met |
| Prompt is the product | The **control system** is the product |
| Hidden retry wrappers | Immutable **signals** and append-only **events** |
| Graph = the application | Graph = **topology** inside a versioned **specification** |
| Chat UI | Industrial **control console** |

If you want a DAG of tools, use a workflow engine. If you want a conversation, use a chat product. If you want **stability, gain, oscillation detection, and convergence** around model output, use Actuate.

## The idea

Classical control maps onto Actuate one-to-one:

| Control theory | Actuate |
|---|---|
| Plant | `Generator` (LLM / NVIDIA NIM / custom OpenAI-compatible endpoint / stub) |
| Sensor | `Evaluator` (`RuleEvaluator`, `LLMJudgeEvaluator`, `SimilarityEvaluator`) |
| Error | `ErrorSignal` (setpoint − measured) |
| Controller | Topology-blind `Controller` (rule-based or PID) |
| Actuator | `Corrector` (`PromptCorrector`, strategy / context / output) |
| Setpoint | `SetPoint.target` |
| Stability / saturation | `StabilityGuard` (max iterations, timeout) |
| Oscillation | `ConvergencePolicy` |
| Feedback path | Plant output structurally reaches an actuator (policy, default on) |

**Signals** are values on the wire (never mutated). **Events** are facts in the log (never rewritten). Iterations, status, metrics, and convergence progress are **projections** of the event stream — not a second mutable database.

**Runtime vs history:** an `ExecutionSession` is the live in-memory cursor. A `Run` is the persisted historical record.

## Big picture

```
Developer / API / UI
        │
        ▼
┌───────────────────────────────────────────┐
│              Presentation                 │
│     React console · FastAPI · WebSocket   │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│         ControlSystem (aggregate)         │
│  Specification (immutable, versioned)     │
│    └── Topology (nodes, ports, edges)     │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│            ExecutionEngine                │
│  walks topology · fans events to sinks    │
│  Controller (decide)  Scheduler (dispatch)│
└───────────────────────────────────────────┘
        │
   Signals on ports
        │
   ┌────┴─────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼
 Plant     Sensor     Merge     Actuator
 (LLM)    (quality)  (error)   (correct)
   │          │          │          │
   └──────────┴──────────┴──────────┘
              ↺ feedback
        │
        ▼
 EventLog → Postgres  ·  OpenTelemetry  ·  live UI
```

### Domain hierarchy

```
Workspace
  └── ControlSystem          # what the user is building
        └── Specification    # immutable snapshot: topology + policy + bindings
              └── Run        # one execution (event-sourced)
                    └── Iteration  # projection: one pass around the feedback path
```

A **graph** is how topology is represented (NetworkX + port-typed edges). It is not the aggregate root.

## Architecture

Full frozen design: [`docs/architecture/FROZEN_ARCHITECTURE.md`](docs/architecture/FROZEN_ARCHITECTURE.md)

| Layer | Responsibility | Not responsible for |
|---|---|---|
| `actuate.domain` | Types: signals, events, topology, policy, registry | I/O |
| `actuate.engine` | Walk topology, invoke capabilities, append events | Control law, SQL, HTTP |
| `Controller` | Error + objective + history → control decision | Graph traversal |
| `Scheduler` | Sequential / future parallel dispatch | What to run |
| `RunStore` | Durable workspace / system / spec / event log | Binary blobs |
| `EventSink` | Trace, persist, WebSocket, MLflow | Orchestration |
| `CapabilityRegistry` | Discover and instantiate plugins | Execution |

**Capabilities** (not hard-coded classes) register plants, sensors, actuators, controllers, fusion, retry, stores, and sinks. Each descriptor carries id, version, author, description, config schema, and compatibility.

**Memory ≠ retrieval.** A `MemoryStore` holds records. A `MemoryRetriever` recalls them. A `MemorySignal` carries recalled context — never the store itself. A small **learning graph** indexes successful corrections for later runs.

**Feedback-path validation** is a policy: default `RequireFeedbackPath`, opt-in `AllowAnyTopology` for authoring fragments.

## Repository layout

```
actuate/
  domain/          ControlSystem, Specification, Topology, Signals, Events, ExecutionSession
  engine/          ExecutionEngine, controllers, fusion, scheduler, NetworkX helper
  plants/          StubGenerator, LiteLLMAdapter (OpenAI, Anthropic, Gemini, Groq,
                   OpenRouter, NVIDIA NIM, Ollama, custom OpenAI-compatible)
  sensors/         RuleEvaluator, LLMJudgeEvaluator, SimilarityEvaluator
  actuators/       PromptCorrector, OutputCorrector, ContextCorrector, StrategyCorrector
  retry/           Exponential, diversity, temperature sweep, model switch, perturbation
  memory/          Vector store + cosine retriever + learning graph
  persistence/     InMemoryRunStore, SqlRunStore (Postgres), bootstrap seed
  telemetry/       Tracing / persistence / MLflow event sinks
  dsl/             YAML → Specification
  plugins/         Built-in capability registration
  api/             FastAPI + WebSocket control plane
ui/frontend/       React control console (Vite)
docs/architecture/ Frozen architecture
tests/             Engine, codec, API, bootstrap
docker-compose.yml Postgres 16
```

## Quick start

### 1. Clone

```bash
git clone https://github.com/actuate-ai/actuate.git
cd actuate
```

Replace `actuate-ai/actuate` with your fork if you have not published the canonical repo yet.

### 2. Postgres

```bash
docker compose up -d postgres
```

PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg://actuate:actuate@localhost:5432/actuate"
```

Unix:

```bash
export DATABASE_URL=postgresql+psycopg://actuate:actuate@localhost:5432/actuate
```

### 3. Install and boot the API

```powershell
pip install -e ".[ui,persistence,plants,dsl,dev]"
python -m actuate.api
```

On Windows, Actuate forces `WindowsSelectorEventLoopPolicy` so psycopg can talk to Postgres (the default Proactor loop is incompatible).

Startup **bootstraps** Postgres (idempotent): default workspace, four control systems, specifications, and NVIDIA/Ollama API base URLs. Existing API keys are never overwritten.

Re-run seed anytime:

```powershell
python -m actuate.persistence.bootstrap
# or
actuate-bootstrap
```

Without `DATABASE_URL`, the same seed fills an in-memory store (demo only). Production persistence is **Postgres only**.

### 4. Control console

```powershell
cd ui/frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

**First loop with no keys:** New Run → provider **Stub (offline)** → required phrase `MUST-INCLUDE` → Start loop. Watch Live Session.

**NVIDIA (trial / free-tier NIM):** Settings → NVIDIA NIM → paste `nvapi-…` from [build.nvidia.com](https://build.nvidia.com) → New Run → NVIDIA → pick `meta/llama-3.1-8b-instruct`.

**Any OpenAI-compatible server:** New Run → **Custom OpenAI-compatible** → paste base URL (`https://host/v1`), API key, and model name.

## Control console

| Screen | Role |
|---|---|
| Dashboard | Operational KPIs over event-sourced runs |
| New Run | Prompt, provider, model, gain, sensors, actuators, custom URL/key |
| Live Session | Feedback graph, iteration timeline, diffs, live WebSocket events |
| Runs | Historical executions |
| Loop Designer | Closed-loop topology (React Flow) |
| Models | Provider catalog and configuration state |
| Plugins | Capability registry (kind, version, author) |
| Observability | Score, latency, tokens projected from the event log |
| Settings | Persist keys + custom bases to Postgres |

## Models and plants

| Provider | How |
|---|---|
| Stub | Offline plant for CI and first-run demos |
| OpenAI, Anthropic, Gemini, Groq, OpenRouter | LiteLLM + env / Settings keys |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` + `NVIDIA_API_KEY` |
| Ollama | Local `http://localhost:11434` |
| **Custom** | Your URL + key + model (OpenAI chat-completions compatible) |

## Bootstrapped Postgres rows

Inserted on first start if missing:

| ID | What |
|---|---|
| `actuate000000000000000000000001` | Workspace **Actuate** |
| `cs_offline_stub` | Offline stub demo control system |
| `cs_nvidia_nim` | NVIDIA NIM loop |
| `cs_custom_endpoint` | Custom OpenAI-compatible loop |
| `cs_json_refiner` | JSON rule-sensor loop |
| `nvidia_base` | `https://integrate.api.nvidia.com/v1` (URL only, no secret) |

## Example (library)

```python
import asyncio
from actuate.domain.policy import LoopPolicy, SetPoint, StabilityGuard
from actuate.domain.specification import create_specification
from actuate.domain.templates import standard_closed_loop
from actuate.engine import ExecutionEngine
from actuate.plugins import register_builtins

async def main() -> None:
    spec = create_specification(
        control_system_id="demo",
        version_number=1,
        topology=standard_closed_loop(
            plant_name="stub",
            sensor_name="rule",
            sensor_params={"required_phrases": ["MUST-INCLUDE"]},
        ),
        policies=LoopPolicy(set_point=SetPoint(target=0.95), stability=StabilityGuard(max_iterations=6)),
    )
    run = await ExecutionEngine().run(
        spec, registry=register_builtins(), initial_prompt="Write a short answer."
    )
    print(run.id)

asyncio.run(main())
```

## Tests

```powershell
pytest tests -q
```

## Star, fork, clone

When this repository is on GitHub:

```bash
# clone
git clone https://github.com/actuate-ai/actuate.git

# fork via GitHub UI, then
git clone https://github.com/<you>/actuate.git
git remote add upstream https://github.com/actuate-ai/actuate.git
```

Star the repo if the control-systems framing is useful. Fork to experiment with controllers, plants, or a different scheduler. Open issues for defects; the architecture document is frozen — implementation and capabilities are where change belongs.

Update the badge URLs (`actuate-ai/actuate`) to your org/repo after the first push so stars, forks, and issues render live.

## Contributing

1. Keep `ControlSystem` as the aggregate root; do not promote Graph or Loop to product identity.
2. Controllers stay topology-blind.
3. Events remain append-only; signals remain immutable.
4. New behavior ships as a **capability**, not a special case in `ExecutionEngine`.
5. Postgres is the production `RunStore`. Do not add SQLite as a product backend.

## License

Apache License 2.0. See [`LICENSE`](LICENSE) when present; `pyproject.toml` already declares Apache-2.0.

---

<p align="center">
  <sub>Traditional AI generates once. Actuate measures, evaluates, corrects, and converges.</sub>
</p>
