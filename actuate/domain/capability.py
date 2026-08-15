"""actuate.domain.capability — the vocabulary for pluggable behavior.

`CapabilityKind` is deliberately an open string namespace, not a closed
enum: core kinds ship built in (see `CapabilityKinds` below), third
parties register more without a core code change. Each *foundational*
kind still has a typed Protocol behind it (see `protocols.py`) — the
open namespace doesn't sacrifice type safety for the well-known
extension points, it just doesn't hardcode the *complete* list.

`CapabilityDescriptor` carries the metadata a registry needs for
discovery/tooling (identifier, version, author, description, supported
configuration schema, compatibility info) — richer than a bare
name -> factory mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CapabilityKind = str


class CapabilityKinds:
    """String constants for the capability kinds Actuate ships with.
    Not exhaustive by design — plugins may register any other string.
    """

    PLANT = "plant"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    ACTUATOR = "actuator"
    SIGNAL_FUSION_STRATEGY = "merge.fusion_strategy"
    ROUTING_STRATEGY = "router.routing_strategy"
    SCHEDULER = "scheduler"
    RUN_STORE = "run_store"
    ARTIFACT_STORE = "artifact_store"
    EVENT_SINK = "event_sink"
    TELEMETRY_EVENT_SINK = "event_sink.telemetry"
    MEMORY_STORE = "memory_store"
    MEMORY_RETRIEVER = "memory_retriever"
    CONVERGENCE_POLICY = "convergence_policy"
    TOPOLOGY_VALIDATION_POLICY = "topology_validation_policy"
    RETRY_HANDLER = "retry_handler"
    DISTURBANCE_INJECTOR = "disturbance_injector"
    EXECUTION_ENGINE = "execution_engine"


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityRef:
    """What a `Node` (domain.nodes) points at: which registered
    capability instance fills this node's slot, plus construction params.
    """

    kind: CapabilityKind
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityDescriptor:
    """Discovery/tooling metadata about one registered capability."""

    kind: CapabilityKind
    name: str
    version: str = "0.0.0"
    author: str = ""
    description: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    compatible_with: tuple[str, ...] = ()
