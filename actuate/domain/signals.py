"""actuate.domain.signals — the data that flows on the wires between
node ports. Every Signal is immutable (frozen dataclass) once produced.

Metadata carried on every Signal (per the frozen architecture review):
`id`, `correlation_id` (ties every signal produced within one Run
together), `parent_signal_id` (the causal predecessor — e.g. an
ObservationSignal's parent is the OutputSignal it scored), `produced_by_node`
/ `produced_by_port`, `produced_at`, `schema_version` (for forward
compatibility as payload shapes evolve), and an open `metadata` dict for
anything else. This is what makes a Signal fully traceable through a
distributed or replayed execution, not just a same-process return value.

Large/binary payloads (images, audio) are never inlined — they're
referenced via `ArtifactRef` into an `ArtifactStore`, keeping every
Signal small and cheap to log/replay regardless of Plant modality.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactRef:
    """A pointer into an ArtifactStore, not the payload itself."""

    store_key: str
    media_type: str
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryRecord:
    text: str
    score: float
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class Signal:
    """Base class for every signal kind. Never instantiated directly."""

    id: str = field(default_factory=_new_id)
    correlation_id: str
    parent_signal_id: str | None = None
    produced_by_node: str
    produced_by_port: str
    produced_at: float = field(default_factory=time.time)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class PromptSignal(Signal):
    """Carries the reference input going into a Plant node."""

    text: str
    artifacts: tuple[ArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputSignal(Signal):
    """A Plant's raw output — the "measured output" of the system."""

    text: str
    artifacts: tuple[ArtifactRef, ...] = ()
    latency_seconds: float = 0.0
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationSignal(Signal):
    """One Sensor's reading of an OutputSignal."""

    sensor_id: str
    score: float  # normalized to [0, 1]
    passed: bool
    feedback: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorSignal(Signal):
    """The aggregated deviation from setpoint, computed by a Merge node's
    bound SignalFusionStrategy from one or more ObservationSignals.
    """

    setpoint: float
    measured: float
    error: float
    within_tolerance: bool


ActionKind = Literal["input_mutation", "policy_retune"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlSignal(Signal):
    """An Actuator's output. `action_kind` matches which output port
    produced it (`prompt_mutation` vs. `policy_retune`) — see the node
    taxonomy; the two payload shapes are mutually exclusive by construction.
    """

    actuator_id: str
    action_kind: ActionKind
    revised_prompt: str | None = None  # set iff action_kind == "input_mutation"
    policy_adjustment: dict[str, Any] | None = None  # set iff action_kind == "policy_retune"
    notes: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextSignal(Signal):
    """Typed carrier replacing the old free-form `context: dict` /
    scratch-state hack. `plugin_scratch` is namespaced by plugin/capability
    id so third-party extensions get a sandboxed slot instead of writing
    arbitrary top-level keys that can collide.
    """

    model_params: dict[str, Any] = field(default_factory=dict)
    plugin_scratch: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class MemorySignal(Signal):
    """Carries recalled context — never the memory store itself. Produced
    by a `memory` node's bound MemoryRetriever capability.
    """

    recalled: tuple[MemoryRecord, ...] = ()
