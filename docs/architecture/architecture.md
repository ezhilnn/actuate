# Actuate architecture

This is the architecture of the **running product**, not the old planning
notes (the “11 points” used while the project was being designed).

Actuate is a **closed-loop control system for generative models**, plus a
**control console**. Other Python apps use it as a library: they pass a
**plant configuration** (model + API key + optional base URL) and a
**prompt**. Actuate makes the LLM calls. Callers do not inject completions.

---

## What it is

Traditional stack:

```
your app → LLM API → one response
```

Actuate:

```
your app → Actuate (setpoint, plant, sensor, controller)
                │
                ▼
         LLM API (plant)  ↺  until quality hits the target
                │
                ▼
         Run (events, scores, tokens) → your app
```

The LLM is a **plant**. Quality is **measured**. The gap from target is
**error**. A revised prompt is **actuation**. Stopping is **converged**,
**exhausted**, **oscillating**, **timeout**, or **token budget** — not
“the model finished talking.”

A **graph of specialists** is optional topology inside that story. The
graph is not the product identity.

---

## Big picture

```
┌─────────────────────────────────────────────────────────────┐
│  Callers                                                     │
│  Python library  ·  FastAPI console  ·  React UI             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Domain                                                      │
│  Workspace → ControlSystem → Specification → Run             │
│  Topology (nodes/ports/edges) · Signals · Events · Policy    │
└──────────────────────────────┬──────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ Closed loop             │       │ Specialist DAG          │
│ ExecutionEngine         │       │ GraphRunner             │
│ plant → sensor → error  │       │ parallel ready nodes    │
│ → controller → actuator │       │ agents + tools + judges │
└────────────┬────────────┘       └────────────┬────────────┘
             │                                 │
             └────────────┬────────────────────┘
                          ▼
                 Generator (plant)
                 LiteLLMAdapter / Stub (tests)
                          │
                          ▼
              OpenAI · NVIDIA NIM · Anthropic · …
                          │
                          ▼
        Postgres (events, graph_runs, memory, keys)
        or in-memory store (local demo)
```

---

## Domain objects

| Object | Role |
|---|---|
| **Workspace** | Tenant / project container |
| **ControlSystem** | Aggregate root — the thing the user is building |
| **Specification** | Immutable snapshot: topology + setpoint + stability + actuation policy |
| **Topology** | Nodes, ports, edges. A graph drawing is this structure, not a second product |
| **Run** | One execution. History is the **append-only event log** |
| **Iteration** | Projection of events for one pass around the feedback path |
| **Signal** | Immutable value on a port (prompt, output, observation, error, control) |
| **Event** | Fact in the log (never rewritten) |
| **Capability** | Plugin slot: plant, sensor, actuator, controller, fusion, retry |

**Controllers are topology-blind.** They see error, setpoint, and recent
history — not the graph layout.

**Default loop shape:** plant → sensor(s) → merge → controller → actuator ↺ plant.

---

## Two runtimes

### 1. Closed loop — `ExecutionEngine`

Used by New Run → Control loop, Live Session, and library embeds.

1. Resolve the plant from the specification (`litellm` + your model/key).
2. Call the LLM with the current prompt.
3. Sensor scores the output (rules, LLM judge, or similarity).
4. Error = setpoint − measured.
5. Controller says revise or publish.
6. Actuator rewrites the prompt if needed.
7. Repeat until policy says stop (`min_iterations`, max iterations, convergence, oscillation, timeout).

### 2. Specialist DAG — `GraphRunner`

Used by New Run → Multi-agent graph, Loop Designer, and library embeds.

- Nodes are catalog specialists (researcher, epidemiologist, judges, …).
- Each specialist is an **agent**: LLM plus tools (`web_search`, `http_get`,
  `recall_memory`, `calculator`, `utc_now`, `list_connections`, `handoff`).
- When a node finishes, **every unblocked child starts together**.
- A child with extra unfinished parents waits.
- Stop when judges pass, passes exhaust, or the **token budget** trips.
- **Rerun from a node** freezes ancestors and starts a new run id.

Judges are quality gates, not a second aggregate root.

---

## How another Python app uses Actuate

You do **not** run the LLM yourself and “hand the answer to Actuate.”
You hand Actuate **how to call the LLM**. Actuate is the loop.

### Closed loop (quality until setpoint)

```python
import asyncio
from actuate.domain.policy import LoopPolicy, SetPoint, StabilityGuard
from actuate.domain.specification import create_specification
from actuate.domain.templates import standard_closed_loop
from actuate.engine import ExecutionEngine
from actuate.plugins import register_builtins

async def main() -> None:
    spec = create_specification(
        control_system_id="my-app",
        version_number=1,
        topology=standard_closed_loop(
            plant_name="litellm",
            plant_params={
                "model": "openai/meta/llama-3.1-8b-instruct",
                "api_base": "https://integrate.api.nvidia.com/v1",
                "api_key": "nvapi-...",          # or os.environ["NVIDIA_API_KEY"]
                "temperature": 0.2,
            },
            sensor_name="llm_judge",
        ),
        policies=LoopPolicy(
            set_point=SetPoint(target=0.9),
            stability=StabilityGuard(max_iterations=6, min_iterations=3),
        ),
    )
    run = await ExecutionEngine().run(
        spec,
        registry=register_builtins(),
        initial_prompt="Write a cautious boil-water brief. NEED SOURCE if unsure.",
    )
    print(run.id)

asyncio.run(main())
```

`plant_params` is forwarded to `LiteLLMAdapter`. That adapter calls
chat-completions. OpenAI is the same shape with `model="gpt-4o-mini"`
and `api_key=os.environ["OPENAI_API_KEY"]` (no custom `api_base`
required).

### Specialist graph (many agents, one plant)

```python
import asyncio
from actuate.graphs import GraphRunner, templates
from actuate.plants import LiteLLMAdapter

async def main() -> None:
    plant = LiteLLMAdapter(
        model="gpt-4o-mini",
        api_key="sk-...",
        temperature=0.2,
    )
    graph = next(t for t in templates() if t["id"] == "public_health_ops")
    result = await GraphRunner(plant, max_tokens=80_000).run(
        graph,
        prompt="Your user-facing task here.",
    )
    print(result["status"], result["output"][:500], result["tokens"])

asyncio.run(main())
```

Same idea: **one plant object**, Actuate fans it across nodes (in
parallel when the DAG allows). Tools run inside those nodes.

### What you pass vs what you get back

| You pass | Actuate does | You get |
|---|---|---|
| Model id, API key, optional `api_base` | HTTP to the LLM | You never see raw HTTP unless you log it |
| User prompt / goal | Iterations or DAG | Final text, scores, tokens, traces/events |
| Optional Postgres URL | Persist runs/memory | Same APIs after restart |
| Optional memory object | Recall on later runs | Indexed successes |

Install: `pip install -e ".[plants]"` (add `persistence` / `ui` as needed).
Copy-paste samples: [`examples/closed_loop.py`](../../examples/closed_loop.py),
[`examples/graph_lab.py`](../../examples/graph_lab.py).

The **console** is the same engines behind HTTP. Settings stores keys in
Postgres; New Run builds the same `plant_params` for you.

---

## Console

| Piece | Role |
|---|---|
| `python -m actuate.api` | FastAPI + WebSocket on port 8000 |
| `ui/frontend` | React operator UI on 5173 |
| Auth | Console token (`ACTUATE_AUTH`, default on) |
| Screens | Dashboard, New Run, Live Session, graph inspector, Designer, Benchmarks, Memory, Settings |

---

## Persistence and memory

Production store is **Postgres** (`DATABASE_URL`). Tables include events,
specifications, workspaces, control systems, keychain, `graph_runs`,
`memory_records`. SQLite is not a product backend. Without
`DATABASE_URL`, an in-memory store is demo-only.

Successful loop/graph outputs can be indexed and recalled on later
plants (`retrieved_context`).

---

## Tokens

Live calls use provider `usage.prompt_tokens + usage.completion_tokens`.
If the provider returns zeros, Actuate uses `len(text) // 4`. Graph
budgets sum every specialist/judge/tool round. This is metering, not a
billing tokenizer.

---

## Constraints that still hold

1. **ControlSystem** is the aggregate root — not Graph, not LoopRunner.
2. Controllers do not traverse topology.
3. Signals are immutable; events are append-only.
4. New plant/sensor/actuator types register as **capabilities**.
5. Postgres is the product `RunStore`.
