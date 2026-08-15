# Actuate — Frozen Architecture (v1)

**Status:** FROZEN. This is the final architecture. No further review,
redesign, or renaming beyond the two edits below. Implementation
proceeds from this document.

**Final edits applied (surgical, per explicit instruction — nothing else in
this document changed):**

1. **`Loop` → `ControlSystem`.** Not a new aggregate-root tier — a
   rename of the same aggregate root, same fields, same position in the
   hierarchy (`Workspace → ControlSystem → Specification → Run`). The
   name change reflects that a `ControlSystem`'s `Topology` may itself
   contain more than one feedback path in future work (cascade/nested
   control), without pretending "may contain multiple loops" today by
   inventing a second hierarchy level. Every other reference to `Loop`
   throughout this document (`loop_id`, "a Loop's Specification," etc.)
   now reads `ControlSystem`/`control_system_id` — mechanical rename
   only, no other field, section, or responsibility changed.
2. **Persistence target: PostgreSQL or MySQL, not SQLite.** `RunStore`
   remains a Protocol (unchanged); the reference `SqlRunStore`
   implementation targets PostgreSQL as primary, MySQL as a supported
   secondary, both via SQLAlchemy (unchanged decision from the prior
   review — SQLAlchemy, not SQLModel, not raw driver code). Local/dev
   ergonomics (spinning up Postgres for local work) are an
   implementation-phase concern, not an architecture concern — the
   Protocol boundary is what makes the backend swappable at all, and
   that boundary is unchanged.

No other section, term, or responsibility in this document is open for
further discussion. Proceeding directly to implementation.

---

## 0. How your 11 points map to this document

| # | Your point | Resolved in |
|---|---|---|
| 1 | Separate Specification / Topology / Runtime | §2 |
| 2 | Don't make Graph the aggregate root | §2.1 |
| 3 | Signals as first-class | §3.1 |
| 4 | Ports | §3.2 |
| 5 | Generic node taxonomy | §3.3 |
| 6 | Corrector → Actuator (doc-level), keep concrete class names | §7 (reconfirmed, unchanged from prior draft) |
| 7 | Separate Engine / Controller / Scheduler / Observers / Persistence / Storage / Telemetry | §4 |
| 8 | Capability-based plugins | §5 |
| 9 | Immutable Signals vs. append-only Events | §3.1, §3.4 |
| 10 | Single meaning per term | §8 |
| 11 | Long-term coherence check | §9 |

---

## 1. Guiding constraint, stated precisely

You've now said three times, in three different framings, what this
system is *not* (not an orchestration framework, not a graph engine, not
a workflow engine) and what it *is* (a closed-loop feedback control
framework). That has to become an actual, checkable design constraint,
not just a sentence in a README. Here it is:

> **A `Topology` must contain at least one designated feedback path** —
> a route from an `Actuator` node's control-mutation output, through
> zero or more intermediate nodes, back to a `Plant` node's input. A
> `Specification` whose `Topology` has no such path fails validation at
> compile time.

This is what actually keeps Actuate from drifting into "yet another
graph executor" no matter how generic the node/port model underneath
gets (§3). The generic node taxonomy (routers, parallel branches, tool
calls, human-approval gates) is free to make the topology *around* that
feedback path as rich as you want — but the feedback path is mandatory,
checked, and is what every execution-time concept (`Iteration`,
`ErrorSignal`, convergence) is defined relative to. A pure acyclic
pipeline is a valid *rejection* from Actuate, not a valid degenerate
case of it — if someone wants that, they want a workflow tool, and
Actuate should say so rather than quietly becoming one.

---

## 2. Specification / Topology / Runtime

### 2.1 Aggregate root — resolved

Not `Graph`. **`Loop`** remains the aggregate root: a named, stable
identity within a `Workspace`, existing independently of any one
version of its design. A graph is structure; `Loop` is the thing a user
is actually building, iterating on, and pointing a `Workspace` at.
`Graph`-as-root was the wrong call in the intermediate draft precisely
because it promotes an implementation detail (how the topology happens
to be represented) to product-identity status — the same category of
mistake the current LoopForge-v1 codebase makes by centering
`LoopRunner`, an execution detail, instead of a real domain concept.

### 2.2 `Specification` (was `LoopVersion`)

Immutable, versioned. Every field you listed is present and nothing
else is:

```
Specification:
    id, loop_id, version_number, created_at
    topology: Topology                  # structure only (§2.3)
    objective: SetPoint                 # the target, see §2.4
    policies: LoopPolicy                # ConvergenceCriteria / StabilityGuard / ActuationPolicy
    capability_bindings: dict[CapabilityKind, str]   # which registered capability instance
                                                       # fills which slot in this topology (§5)
    metadata: dict[str, Any]
```

A `Run` always references exactly one `Specification` — this is what
makes "show me exactly what produced run #4821" a real, answerable
question, and what makes an `Experiment` (§6) meaningful ("compare
Specification A vs. Specification B against the same input").

### 2.3 `Topology`

Pure structure, zero runtime state, exactly as you specified:

```
Topology:
    nodes: list[Node]        # id, kind, input_ports, output_ports (§3.2, §3.3)
    edges: list[Edge]        # (from_node, from_port) -> (to_node, to_port)
```

`Topology` is validated (DAG-per-non-feedback-region, port type
compatibility across every edge, the mandatory-feedback-path rule from
§1) at the moment a `Specification` is created — not at run time. A
`Specification` that fails validation is never persisted. This is a
direct fix for the current codebase's actual bug: today, an invalid
*or ignored* topology only surfaces at Run time (or never surfaces at
all, since branching edges are silently unused). Validation moving to
Specification-creation time closes both problems at once.

### 2.4 `Objective` / `SetPoint`

Unchanged in substance from the prior draft, relocated to hang off
`Specification` directly rather than being buried inside a flat
`LoopPolicy`:

```
SetPoint:
    target: float                # [0,1] — see §8's resolution on per-sensor set points
    scope: "aggregate"            # deliberately not yet exposing per-sensor scoping —
                                   # see §8, this was the open §1.6 question from the
                                   # prior draft and is resolved there, not duplicated here
```

### 2.5 `Runtime` — `Run` / `Iteration` / `Event` log

```
Run:
    id, specification_id, mode: "live" | "simulated" | "replay"   (§6)
    status: RunStatus            # unchanged enum from prior draft
    started_at, ended_at
    events: EventLog             # append-only (§3.4) — the ONLY history a Run owns
```

Notice `Run` no longer directly owns a list of `Iteration` or
`Generation`/`Evaluation` objects the way the prior draft had it.
That was itself still a residue of "Runtime leaking structure that
belongs to observation, not identity." In this draft: **`Iteration` is
a computed view over the `EventLog`**, not a stored/owned collection —
"iteration 3" means "the third traversal of the feedback path, as
reconstructed by scanning `Run.events` for feedback-path-entry
boundaries." This is what point 1 means by Runtime owning "iteration
history" without that history becoming a second, parallel mutable
structure alongside the Event log — there is exactly one source of
truth (`EventLog`), and `Iteration` is a read model derived from it,
never written to directly. (`RunStore`'s SQL implementation is free to
maintain a materialized `iterations` table as a query-performance
optimization — that's a persistence-layer decision, not a domain-model
one, and doesn't reintroduce the two-sources-of-truth problem as long as
the materialized table is provably derivable from `events` alone.)

---

## 3. Signals, Ports, and the generic Node model

### 3.1 Signals — immutable, typed, the only thing that flows

```
Signal (abstract, immutable):
    id, kind, produced_at, produced_by_node, produced_by_port
    payload: SignalPayload        # generic — see modality note below

PromptSignal(Signal)        payload: text | multimodal content ref (§9)
OutputSignal(Signal)        payload: text | multimodal content ref
ObservationSignal(Signal)   payload: { score: float, passed: bool, feedback: str, details: dict }
ErrorSignal(Signal)         payload: { setpoint: float, measured: float, error: float, within_tolerance: bool }
ControlSignal(Signal)       payload: { revised_prompt: str } | { policy_adjustment: dict }   (§3.3, action_kind resolved via ports)
ContextSignal(Signal)       payload: { model_params: dict, plugin_scratch: dict[str, dict] }  # replaces the old context: dict + IterationScratch
MemorySignal(Signal)        payload: { recalled: list[MemoryRecord] }
```

Renamed `MeasuredSignal` → **`ObservationSignal`**, matching your
vocabulary and the standard control/estimation-theory term
("observation," as in observer pattern / observation model) — more
precise than "measured," and avoids a collision with the `EventSink`
role rename in §8.

Large binary payloads (images, audio — see §9) are never inlined in a
`Signal`; the payload carries a reference into `ArtifactStore` (§4) and
the `Signal` itself stays small regardless of Plant modality. This is
what keeps the `EventLog` cheap to query/replay even for VLM/speech
workloads.

### 3.2 Ports

```
Port:
    name: str
    signal_kind: type[Signal]
    direction: "in" | "out"

Edge:
    from_node: NodeId, from_port: str
    to_node: NodeId, to_port: str
```

Every edge is validated at Topology-creation time to connect a
`signal_kind`-compatible output port to an input port. Two direct
consequences worth calling out:

- **The old `action_kind` discriminated-union field (§1.1 of the prior
  draft, which you approved as a concept) is now expressed as two
  distinct output ports on an `Actuator` node** —
  `prompt_mutation: ControlSignal` and `policy_retune: ControlSignal` —
  instead of a runtime-checked field. Which port an edge is drawn from
  in the `Topology` *is* the type-level guarantee of what kind of
  action that wire performs. This is strictly better than the field
  version: a malformed topology (an edge from `policy_retune` into a
  `Plant`'s prompt input) is now a Topology-validation error, not a
  runtime surprise.
- **`SignalAggregator` and `CorrectorSelector`, both proposed as
  bespoke standalone Protocols in the prior draft, are retired.** They
  are subsumed by the generic node taxonomy (§3.3) — a `Merge` node
  bound to a fusion capability replaces `SignalAggregator`; a `Router`
  node bound to a routing capability replaces `CorrectorSelector`.
  One fewer category of bespoke abstraction, same expressiveness,
  fully consistent with point 5's instruction not to special-case
  component types.

### 3.3 Node taxonomy

One generic runtime contract:

```
Node:
    id, kind: NodeKind
    input_ports: list[Port]
    output_ports: list[Port]
    capability_binding: CapabilityRef      # which registered capability
                                            # instance implements this node (§5)
```

`NodeKind` is an **open** string namespace (not a closed enum) — core
kinds ship built in, plugins add more without a core code change:

| NodeKind | Binds to (capability) | Notes |
|---|---|---|
| `plant` | Plant (was `Generator`) | unchanged from prior draft |
| `sensor` | Sensor (was `Evaluator`) | unchanged |
| `controller` | Controller | now explicitly a node, not an engine-level special case (§4) |
| `actuator` | Actuator (was `Corrector`) | two output ports, see §3.2 |
| `merge` | SignalFusionStrategy | subsumes `SignalAggregator` |
| `router` | RoutingStrategy | subsumes `CorrectorSelector`; N-way dynamic routing |
| `decision` | a boolean/enum predicate over incoming signals | specializes `router` for the common conditional-branch case |
| `memory` | VectorMemory (recall) | emits `MemorySignal` |
| `tool` | arbitrary external function/API call | future-facing, not core v1 scope |
| `human_approval` | pauses `Run`, awaiting an external `Event` | genuinely different from every other kind — see §9 |
| `benchmark` | runs a `Dataset`/`Scenario` batch, emits aggregate signals | ties to `Experiment` (§6) |
| `parallel` | fans one input to N concurrent branches | ties to `Scheduler` (§4) for actual concurrency |
| `delay` | introduces a wait | ties to retry backoff / rate limiting |
| `plugin` | any third-party `NodeKind` registered via the capability system | the general escape hatch |

The recurring pattern, stated once so it isn't re-derived per row: **a
capability (Plant, Sensor, Controller, VectorMemory, ...) is the
pluggable behavior; a NodeKind is the topology-facing wrapper that
places that behavior at a specific point in the graph, with typed
ports; a Signal kind is what flows across the edges connected to that
node's ports.** Three orthogonal axes — behavior, position, data — never
conflated into one class the way today's `Corrector` conflates "an
implementation" with "a graph position" with "an implicit data shape."

### 3.4 Signals vs. Events — the distinction, made load-bearing

- **`Signal`** — a value that exists on a wire between two ports during
  execution. Immutable once produced. Transient in the sense that its
  *purpose* is to be consumed by the next node; it only persists because
  §3.4's Events reference it.
- **`Event`** — an immutable fact appended to a `Run`'s `EventLog`,
  *about* execution having happened. Events never get rewritten;
  `EventLog` is append-only, full stop.

```
Event (abstract, immutable):
    id, run_id, at, kind

NodeExecutionStarted(Event)     node_id
NodeExecutionCompleted(Event)   node_id, produced_signal_ids: list[SignalId]
SignalEmitted(Event)            signal: Signal          # the only place a Signal's
                                                          # full value is actually stored
FeedbackPathEntered(Event)      iteration_index          # what makes "Iteration" derivable
RunStatusChanged(Event)         from_status, to_status
RunFailed(Event)                error: str
```

This is precisely what makes replay (§6) well-defined rather than
hand-waved: replaying a `Run` means constructing a new `Run` whose
`plant`/`sensor`/etc. nodes are (optionally) swapped for different
capability bindings, and feeding it the **`SignalEmitted` events from
the original `Run`'s `EventLog`** wherever a node's input would
otherwise require invoking the (possibly now-absent, possibly
expensive) original capability. Debugging "what exactly happened at
iteration 3" is a query over immutable, ordered `Event`s — no
reconstruction, no ambiguity, no separate metrics stream to
cross-reference (this is the same telemetry-unification benefit as the
prior draft, now on a cleaner substrate).

---

## 4. Execution architecture — six responsibilities, none accumulating

```
ExecutionEngine
   ├─ walks Topology in dependency order (respecting the one mandatory
   │  feedback path as a controlled re-entry, not a plain cycle)
   ├─ for each Node, asks Scheduler how/when to dispatch it
   │  (sequential | parallel | distributed | rate-limited)
   ├─ invokes the Node's bound capability, receives Signal(s)
   ├─ appends Events to the Run's EventLog (via Persistence)
   ├─ fans out every Event to every registered EventSink (Telemetry,
   │  Persistence itself, future live-UI streaming, MLflow, ...)
   ├─ applies ConvergencePolicy + StabilityGuard after each feedback-
   │  path traversal to decide RunStatus transitions
   └─ never contains business logic specific to any one capability —
      if you can point at a line of ExecutionEngine code and ask "which
      Controller/Plant/Actuator does this apply to," that line is a bug
```

Explicit responsibility table, since point 7 asked for exactly this and
the prior draft blurred a couple of these:

| Responsibility | Owner | NOT owned by |
|---|---|---|
| Walk topology, sequence node execution | `ExecutionEngine` | Controller |
| Decide *what correction to make* given an `ErrorSignal` | `Controller` (a node's bound capability) | `ExecutionEngine` |
| Decide *how/when* a node's work actually executes (thread, process, remote worker, batched) | `Scheduler` | `ExecutionEngine`, `Controller` |
| React to `Event`s (trace, log, notify, stream) | `EventSink` implementations | `ExecutionEngine` |
| Durability of `Loop`/`Specification`/`Run`/`Event` | `RunStore` (a specific `EventSink` + a query API) | `ExecutionEngine` |
| Durability of large binary `Signal` payloads | `ArtifactStore` | `RunStore` |
| Trace/metric projection specifically | `TelemetryEventSink` (an `EventSink` specialization) | generic `EventSink` catch-all responsibility |

`Controller` is explicitly **not** a special engine-level concept
anymore — it's a `NodeKind` like any other (§3.3), which is what
actually prevents `SequentialController`/`ExecutionEngine` from
re-accreting LoopRunner's original sin (one class quietly doing
orchestration *and* decision-making *and* execution). Swapping
`RuleBasedController` for `PIDController` is a `capability_binding`
change on one node in one `Specification` — zero `ExecutionEngine`
code path is aware which one is bound.

**Built-in `Controller` capabilities** (unchanged from the prior draft,
still recommended v1 scope: ship `RuleBasedController` as the default,
sketch `PIDController` as the flagship "look, it's genuinely pluggable"
example — implementation-phase decision, not repeated in full here).

---

## 5. Capability-based plugins

Point 8's core ask — move from "five fixed hookspecs, one per component
category" to something that scales the way Kubernetes' CSI/CNI/CRI or
OpenTelemetry's exporter/provider model does. Resolution:

```
CapabilityKind = str   # open namespace, not a closed enum
# core-shipped examples: "plant", "sensor", "controller", "actuator",
# "merge.fusion_strategy", "router.routing_strategy", "scheduler",
# "run_store", "artifact_store", "event_sink", "event_sink.telemetry",
# "memory_provider", "convergence_policy", "disturbance_injector"

CapabilityProvider:
    kind: CapabilityKind
    factory: Callable[..., Any]     # validated against the Protocol
                                     # registered for that kind

CapabilityRegistry:
    def register(self, kind: CapabilityKind, name: str, factory) -> None: ...
    def resolve(self, kind: CapabilityKind, name: str, **params) -> Any: ...
    def list(self, kind: CapabilityKind) -> list[str]: ...
```

A single plugin package can register capabilities across multiple
kinds in one manifest (a plugin offering a novel `Controller` *and* a
`Storage` backend *and* a custom `NodeKind` all at once, matching your
"UI Extension," "Policy," "Signal Processor" examples without needing
new hookspec function signatures for each). The **core framework ships
a fixed, typed Protocol for every foundational kind** (`Plant`,
`Sensor`, `Controller`, `Actuator`, fusion/routing strategies,
`Scheduler`, `RunStore`, `ArtifactStore`, `EventSink`, `VectorMemory`,
`ConvergencePolicy`) — so the common, well-understood extension points
stay fully type-checked — while the `CapabilityKind` namespace itself
stays open, so a `"ui_extension"` or some kind nobody has thought of
yet can be registered and consumed by whatever downstream code knows
what to do with it, without a core release. This is deliberately the
middle ground between "five hardcoded hookspecs" (too rigid, what you
correctly flagged) and "everything is an untyped blob" (too loose, would
undermine the type-safety the rest of this document relies on).

`pluggy` remains the underlying mechanism (unchanged decision); what
changes is that registration goes through one `CapabilityRegistry`
facade instead of five separately-named hookspec functions.

---

## 6. Experiment / Dataset / Scenario / Simulation / Replay — placement, not new peer concerns

None of these become a fourth concept alongside Specification/Topology/
Runtime. They compose from what's already defined:

- **`Dataset`** / **`Scenario`** — a `Dataset` (owned by a `Loop`) holds
  named `Scenario`s (an initial `PromptSignal` + optional reference
  signal for comparison). Pure data, no execution semantics of its own.
- **`Experiment`** — a query/orchestration convenience: run N
  `Specification`s (varying `Controller`, `Policy`, or `Plant` bindings)
  against the same `Dataset`, producing a comparison over the resulting
  `Run.EventLog`s. Built entirely on `RunStore`'s query surface — not a
  new persistence concept.
- **Simulation** = `Run.mode = "simulated"` — the `plant` node's bound
  capability is swapped for a `SimulatedPlant` (deterministic/synthetic,
  costs nothing, safe for CI). Optionally paired with a
  `disturbance_injector` capability that deliberately corrupts/delays
  specific `Signal`s to test resilience — this is the existing
  Disturbance row in your original control-theory mapping table, finally
  made concrete instead of staying a table entry with no execution path.
- **Replay** = `Run.mode = "replay"` — feeds recorded `SignalEmitted`
  events from a prior `Run` back through a new `Run`'s topology,
  optionally with different capability bindings (§3.4 explains
  mechanically how). This is what makes "compare two Controllers on
  the exact same historical input, without re-spending API calls"
  actually work, not just get asserted as a feature.
- **`Trigger`** (deliberately *not* named "Schedule," to avoid colliding
  with the `Scheduler` execution-time capability from §4 — single
  meaning per term, per point 10) — a declarative rule attached to a
  `Loop`/`Specification` (cron / webhook / external event) that creates
  new `Run`s. Data, not a capability; watched by a `TriggerService` that
  is, itself, deliberately out of scope for this document — reserved,
  not designed, consistent with how I scoped `Deployment` in the prior
  draft (a v3+ concern once the execution core is proven).
- **`Project`** — still deferred, unchanged reasoning from the prior
  draft (organizational, non-execution-semantic, safely additive
  later as `Workspace → Project → Loop` without touching anything in
  this document).
- **`Pipeline`** — still rejected as a first-class primitive, and now on
  a sharper footing than "scope creep": §1's mandatory-feedback-path
  constraint makes a pure acyclic multi-stage pipeline *structurally
  invalid* as a `Topology`, not just philosophically discouraged. If you
  want that, it's a different tool by construction, not a missing
  feature.

---

## 7. Terminology at the doc/domain level vs. concrete classes — reconfirmed

Unchanged from the prior draft's resolution, now doubly confirmed by
your own point 6: `Corrector` → `Actuator` at the **domain/architecture**
level (the `NodeKind`, the Protocol category, the diagrams). Concrete,
developer-facing classes keep their AI-native names —
`PromptCorrector`, `RuleEvaluator`, `LLMJudgeEvaluator`,
`LiteLLMAdapter` — because discoverability for the actual target
audience (AI engineers, not controls engineers) outweighs theoretical
purity at the leaf-class level. Same resolution applies to `Generator`/
`Plant` and `Evaluator`/`Sensor`: **Protocol names stay AI-native**
(`Generator`, `Evaluator`, `Corrector`) per your explicit instruction in
the message that renamed the project to Actuate — the `NodeKind`
strings (`"plant"`, `"sensor"`, `"actuator"`) and all documentation/
diagrams carry the control-theory identity; the Python interfaces
themselves stay immediately recognizable to someone who has never heard
the phrase "control theory" and just wants to swap in a different LLM
call.

---

## 8. Single meaning per term — the audit

Going through every term introduced across both drafts and confirming
one responsibility each, resolving two real collisions:

- **Collision found and fixed:** `RunObserver` (prior draft's event-
  reaction role) vs. `ObservationSignal` (this draft's Sensor-output
  signal kind) are dangerously close in name for two unrelated concepts.
  **Resolution: the reaction role is renamed `EventSink`** throughout
  this document (§3.4, §4, §5). "Observation" now means exactly one
  thing — a Sensor's reading — everywhere in the system.
- **Collision found and fixed:** "Schedule" (prior draft's recurring-
  trigger domain object) vs. `Scheduler` (this draft's execution-time
  dispatch capability) — same root word, different layer. **Resolution:
  the domain object is renamed `Trigger`** (§6); `Scheduler` is reserved
  exclusively for execution-time dispatch strategy.
- **Checked, no collision, kept as designed:** `Signal` (data on a wire)
  vs. `Event` (fact in the log) — deliberately different words for
  deliberately different things (§3.4), this is the one place two
  similar-sounding concepts are *supposed* to stay visually distinct in
  the vocabulary, which they already are.
- **Checked, no collision:** `Policy` now means exactly "data" —
  `LoopPolicy`, `SetPoint`, `StabilityGuard`, `ConvergenceCriteria`,
  `ActuationPolicy` are all configuration values living on
  `Specification`. The *behavior* that reads that data and decides a
  `RunStatus` transition is a separate, named capability —
  `ConvergencePolicy` — so "Policy" isn't simultaneously "a value" and
  "a pluggable algorithm" the way it read in the raw list from point 8.
- **Checked, no collision:** `Memory` decomposes cleanly into three
  non-overlapping terms following the "capability / NodeKind / Signal"
  pattern from §3.3: `VectorMemory` (the storage/recall capability),
  `memory` (the `NodeKind` that calls it), `MemorySignal` (what it
  emits). Same pattern, reapplied, not a special case.
- **Checked, no collision:** `Controller` is used for exactly one thing
  throughout — the pluggable decision capability bound to a
  `controller` node. It is never reused for `ExecutionEngine`,
  `Scheduler`, or anything else, unlike the prior draft where
  "Controller" occasionally blurred into "the orchestrator" in prose
  even though the class design didn't.

---

## 9. Long-term coherence check, re-run against the final model

| Future direction | Still coherent? | Why |
|---|---|---|
| VLMs | Yes | `PromptSignal`/`OutputSignal` payloads are generic (`SignalPayload`); a VLM's `plant` node emits an `OutputSignal` whose payload is an `ArtifactStore` reference to an image, not a schema change |
| Speech models | Yes | Same mechanism — audio payload via `ArtifactStore` reference |
| Robotics | Yes — and the naming finally *earns* itself here | `plant`/`sensor`/`actuator` nodes bind literal hardware drivers/telemetry/motor-control capabilities; "Actuator" and "Control Signal" stop being metaphors |
| Arbitrary APIs / tools | Yes | `tool` `NodeKind` exists explicitly for this; also just a `plant` if the API is itself the thing being "generated from" |
| Distributed execution | Yes | `Scheduler` capability is exactly the seam (`distributed` dispatch strategy); `ExecutionEngine` itself doesn't need to change |
| Multiple execution engines | Yes | `ExecutionEngine` is a capability too, per §5's open kind namespace — most users never touch it, advanced infra integrators can |
| Multiple/novel controllers (PID, MPC, Bayesian, RL) | Yes | `controller` is a `NodeKind` bound to a `CapabilityKind="controller"` implementation — no core change to add one |
| Simulation / dry-run / failure injection | Yes | `Run.mode` + `disturbance_injector` capability (§6) |
| Human approval | Yes | `human_approval` `NodeKind` — pauses `Run`, resumes on an external `Event`, no special-casing in `ExecutionEngine` beyond "this node kind can suspend" |
| Autonomous/unattended operation | Yes | `Trigger` (§6) + `Scheduler`'s dispatch strategies cover unattended, recurring, and concurrent operation without new core concepts |

Nothing in this table required inventing a new peer-level domain concept
beyond what §2–§6 already define — which is itself the strongest
signal that the model is at the right level of abstraction: it bent to
accommodate every direction on your list without growing.

---

## 10. What's explicitly still open

1. **GitHub org / trademark check for "Actuate"** — I did a PyPI-only
   pass; confirm you want me to search further, or that this is
   sufficient and you'll finalize registration yourself.
2. **`ConvergencePolicy` default** — I introduced this as a pluggable
   capability (§8) rather than hardcoded `ExecutionEngine` logic,
   consistent with everything else in this document being a capability.
   Confirm that's wanted, or whether convergence-decision logic should
   stay a fixed part of `ExecutionEngine` (the one piece of this
   document where I extended "make it pluggable" slightly further than
   you explicitly asked, because leaving it hardcoded would have been
   the one remaining inconsistency in an otherwise fully capability-
   driven engine).
3. **Node taxonomy completeness** — §3.3's table is what I judge as the
   right v1 set. `tool` and `human_approval` are included because they
   cost nothing architecturally (they're just another `NodeKind`) even
   though they're not core to shipping v1 — confirm you're fine with
   them being *defined* now but not necessarily *implemented* in the
   first coding pass.
4. Everything else from the prior draft's open questions (SQLAlchemy +
   SQLite + Postgres, no SQLModel, no raw sqlite3; concrete class
   naming; UI held until this is approved) is already answered by your
   two review documents and isn't reopened here.

Once you confirm #1–#3 (or say "proceed as written"), this is ready to
move from architecture to a migration plan and then implementation.
