"""actuate.domain.protocols — the foundational, typed extension points.

Naming convention (frozen, per explicit instruction): Protocols use
AI-friendly names (`Generator`, `Evaluator`, `Corrector`) — concrete
implementations (`LiteLLMAdapter`, `RuleEvaluator`, `PromptCorrector`)
stay immediately discoverable to an AI engineer who has never heard the
phrase "control theory." Each Protocol's docstring documents which
control-theory role it fulfills (Plant, Sensor, Actuator, Controller,
...) — the architecture/domain model carries that vocabulary, the code
doesn't have to.

Two-layer separation (see the frozen architecture, §3.3's "capability /
NodeKind / Signal" pattern): every Protocol here takes and returns plain,
ergonomic types (`str`, small dataclasses) — never `Signal`, `Node`,
`Port`, or `Topology`. The engine's per-`NodeKind` adapters are what
translate between the Signal envelope on the wire and these plain
method calls. This is also what makes point 5 of the second review
concrete: a `Controller` implementation literally cannot see topology —
its Protocol signature has no parameter through which one could arrive.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from actuate.domain.events import Event
from actuate.domain.policy import ActuationPolicy, ConvergenceCriteria, SetPoint, StabilityGuard
from actuate.domain.run import IterationView, RunStatus
from actuate.domain.signals import ArtifactRef, ErrorSignal, MemoryRecord, ObservationSignal, Signal

# ---------------------------------------------------------------------
# Plant role
# ---------------------------------------------------------------------


@runtime_checkable
class Generator(Protocol):
    """Fulfills the **Plant** role: the system being controlled."""

    async def generate(self, prompt: str, *, context: dict[str, Any]) -> str: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerationOutcome:
    """Richer return shape for generators that report cost/latency —
    what the `plant` NodeKind adapter uses to populate an OutputSignal's
    `usage`/`latency_seconds` fields.
    """

    text: str
    latency_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class MeteredGenerator(Generator, Protocol):
    """A Generator that can also report its own cost/latency."""

    async def generate_with_metadata(
        self, prompt: str, *, context: dict[str, Any]
    ) -> GenerationOutcome: ...


# ---------------------------------------------------------------------
# Sensor role
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationOutcome:
    score: float
    passed: bool = False
    feedback: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Evaluator(Protocol):
    """Fulfills the **Sensor** role: measures OutputSignal quality."""

    async def evaluate(
        self, *, prompt: str, output: str, context: dict[str, Any]
    ) -> EvaluationOutcome: ...


# ---------------------------------------------------------------------
# Actuator role
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrectionOutcome:
    action_kind: str  # "input_mutation" | "policy_retune" — matches ControlSignal
    revised_prompt: str | None = None
    policy_adjustment: dict[str, Any] | None = None
    notes: str = ""


@runtime_checkable
class Corrector(Protocol):
    """Fulfills the **Actuator** role: turns an error into a control action."""

    async def correct(
        self,
        *,
        prompt: str,
        output: str,
        evaluation: EvaluationOutcome,
        gain: float,
        context: dict[str, Any],
    ) -> CorrectionOutcome: ...


# ---------------------------------------------------------------------
# Controller — deliberately topology-blind (review 2, point 5)
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlDecision:
    actuator_names: tuple[str, ...]
    effective_gain: float
    converged_hint: bool = False
    notes: str = ""


@runtime_checkable
class Controller(Protocol):
    """The pluggable control algorithm. Receives only control-theory
    concepts — error, objective, history — and returns a decision.
    No parameter here can carry a Node, Port, or Topology; this is the
    whole enforcement mechanism for keeping Controllers topology-blind.
    """

    def decide(
        self,
        *,
        error: ErrorSignal,
        objective: SetPoint,
        actuation: ActuationPolicy,
        history: list[IterationView],
        available_actuators: tuple[str, ...],
    ) -> ControlDecision: ...


@runtime_checkable
class ConvergencePolicy(Protocol):
    """Decides whether a Run should stop after this iteration. Pure
    function of the same control-theory concepts a Controller sees, plus
    the algorithm-agnostic safety envelope (StabilityGuard/
    ConvergenceCriteria apply regardless of which Controller is bound).
    """

    def evaluate(
        self,
        *,
        error: ErrorSignal,
        history: list[IterationView],
        convergence: ConvergenceCriteria,
        stability: StabilityGuard,
        iteration_index: int,
        elapsed_seconds: float,
    ) -> RunStatus | None: ...


# ---------------------------------------------------------------------
# Merge / Router node capabilities (subsume SignalAggregator/CorrectorSelector)
# ---------------------------------------------------------------------


@runtime_checkable
class SignalFusionStrategy(Protocol):
    """Bound to a `merge` node: combines one or more ObservationSignals
    into one ErrorSignal, against a SetPoint.
    """

    def fuse(
        self, observations: list[ObservationSignal], *, set_point: SetPoint
    ) -> ErrorSignal: ...


@runtime_checkable
class RoutingStrategy(Protocol):
    """Bound to a `router` node: picks which output port a signal exits
    through.
    """

    def route(self, signal: Signal, *, available_ports: tuple[str, ...]) -> str: ...


# ---------------------------------------------------------------------
# Retry (Plant-level resilience — unchanged in kind from LoopForge v1)
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryAttempt:
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    generator_override: Generator | None = None


@runtime_checkable
class RetryHandler(Protocol):
    def prepare_attempt(
        self, *, attempt: int, prompt: str, context: dict[str, Any], last_error: Exception | None
    ) -> RetryAttempt: ...

    async def wait_before_retry(self, attempt: int) -> None: ...


# ---------------------------------------------------------------------
# Memory — storage vs. retrieval, kept distinct (review 2, point 7)
# ---------------------------------------------------------------------


@runtime_checkable
class MemoryStore(Protocol):
    """Pure storage. No recall/query semantics live here."""

    async def put(self, record: MemoryRecord, *, embedding: list[float]) -> None: ...

    async def count(self) -> int: ...


@runtime_checkable
class MemoryRetriever(Protocol):
    """The recall *operation*, bound to a `memory` node. Reads from a
    MemoryStore internally; returns plain records, not a Signal — the
    `memory` NodeKind adapter wraps the result into a MemorySignal.
    """

    async def recall(self, query: str, *, top_k: int = 5) -> list[MemoryRecord]: ...


# ---------------------------------------------------------------------
# Scheduler — execution-time dispatch strategy only
# ---------------------------------------------------------------------


@runtime_checkable
class Scheduler(Protocol):
    """Decides *how/when* a batch of node-execution tasks actually run
    (sequential, parallel, distributed, rate-limited). Never decides
    *what* runs or *what it means* — those are ExecutionEngine's and
    Controller's jobs respectively.
    """

    async def dispatch(
        self, tasks: list[Callable[[], Awaitable[Any]]]
    ) -> list[Any]: ...


# ---------------------------------------------------------------------
# Persistence / Storage / Telemetry — kept as distinct responsibilities
# ---------------------------------------------------------------------


@runtime_checkable
class EventSink(Protocol):
    """One method — every reaction to execution (tracing, persistence,
    live UI streaming, MLflow, ...) is a subscriber to the same Event
    stream. Named `EventSink`, not `Observer`, specifically to avoid
    colliding with `ObservationSignal` (review 2's terminology audit).
    """

    async def handle(self, event: Event) -> None: ...


@runtime_checkable
class RunStore(Protocol):
    """Durability for structured domain history (Workspace, ControlSystem,
    Specification, Run, Event log). Reference implementation targets
    PostgreSQL/MySQL via SQLAlchemy (frozen architecture, persistence
    decision) — this Protocol has no opinion on which.
    """

    async def append_event(self, event: Event) -> None: ...

    async def load_events(self, run_id: str) -> list[Event]: ...

    async def save_specification(self, specification: Any) -> None: ...

    async def load_specification(self, specification_id: str) -> Any: ...

    async def list_specification_ids(self) -> list[str]: ...

    async def list_run_ids(self) -> list[str]: ...


@runtime_checkable
class ArtifactStore(Protocol):
    """Durability for large/binary Signal payloads — deliberately
    separate from RunStore so structured metadata queries never have to
    scan through image/audio blobs.
    """

    async def put(self, data: bytes, *, media_type: str) -> ArtifactRef: ...

    async def get(self, ref: ArtifactRef) -> bytes: ...
