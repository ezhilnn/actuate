"""JSON codec for Events, Signals, Specifications, and Topology.

Used by SqlRunStore. Domain objects stay dataclasses; this module is the
only place that knows how to round-trip them through JSONB.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from actuate.domain.capability import CapabilityRef
from actuate.domain.events import (
    Event,
    FeedbackPathEntered,
    NodeExecutionCompleted,
    NodeExecutionStarted,
    RunFailed,
    RunStarted,
    RunStatusChanged,
    SignalEmitted,
)
from actuate.domain.nodes import Node
from actuate.domain.policy import LoopPolicy
from actuate.domain.ports import Edge, Port
from actuate.domain.signals import (
    ArtifactRef,
    ContextSignal,
    ControlSignal,
    ErrorSignal,
    MemoryRecord,
    MemorySignal,
    ObservationSignal,
    OutputSignal,
    PromptSignal,
    Signal,
    TokenUsage,
)
from actuate.domain.specification import Specification
from actuate.domain.topology import Topology

_SIGNAL_TYPES: dict[str, type[Signal]] = {
    cls.__name__: cls
    for cls in (
        PromptSignal,
        OutputSignal,
        ObservationSignal,
        ErrorSignal,
        ControlSignal,
        ContextSignal,
        MemorySignal,
    )
}

_EVENT_TYPES: dict[str, type[Event]] = {
    cls.__name__: cls
    for cls in (
        RunStarted,
        NodeExecutionStarted,
        NodeExecutionCompleted,
        SignalEmitted,
        FeedbackPathEntered,
        RunStatusChanged,
        RunFailed,
    )
}

_KIND_BY_NAME: dict[str, type[Signal]] = dict(_SIGNAL_TYPES)


def encode(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        payload: dict[str, Any] = {"__type__": type(obj).__name__}
        for item in fields(obj):
            payload[item.name] = encode(getattr(obj, item.name))
        return payload
    if isinstance(obj, type):
        return {"__type__": "type", "name": obj.__name__}
    if isinstance(obj, tuple):
        return [encode(item) for item in obj]
    if isinstance(obj, dict):
        return {key: encode(value) for key, value in obj.items()}
    return obj


def decode_event(payload: dict[str, Any]) -> Event:
    kind = payload["__type__"]
    cls = _EVENT_TYPES[kind]
    data = {key: value for key, value in payload.items() if key != "__type__"}
    if kind == "SignalEmitted":
        data["signal"] = decode_signal(data["signal"])
        return SignalEmitted(**data)
    if kind == "NodeExecutionCompleted":
        data["produced_signal_ids"] = tuple(data.get("produced_signal_ids") or ())
    return cls(**data)


def decode_signal(payload: dict[str, Any]) -> Signal:
    kind = payload["__type__"]
    cls = _SIGNAL_TYPES[kind]
    data = {key: value for key, value in payload.items() if key != "__type__"}
    if "artifacts" in data and data["artifacts"] is not None:
        data["artifacts"] = tuple(
            ArtifactRef(**_strip_type(item)) if isinstance(item, dict) else item
            for item in data["artifacts"]
        )
    if "usage" in data and isinstance(data["usage"], dict):
        data["usage"] = TokenUsage(**_strip_type(data["usage"]))
    if "recalled" in data and data["recalled"] is not None:
        data["recalled"] = tuple(
            MemoryRecord(**_strip_type(item)) if isinstance(item, dict) else item
            for item in data["recalled"]
        )
    return cls(**data)


def encode_specification(specification: Specification) -> dict[str, Any]:
    return {
        "id": specification.id,
        "control_system_id": specification.control_system_id,
        "version_number": specification.version_number,
        "created_at": specification.created_at,
        "policies": specification.policies.model_dump(),
        "metadata": specification.metadata,
        "topology": {
            "nodes": [encode(node) for node in specification.topology.nodes],
            "edges": [encode(edge) for edge in specification.topology.edges],
        },
    }


def decode_specification(payload: dict[str, Any]) -> Specification:
    nodes = tuple(_decode_node(item) for item in payload["topology"]["nodes"])
    edges = tuple(Edge(**_strip_type(item)) for item in payload["topology"]["edges"])
    return Specification(
        id=payload["id"],
        control_system_id=payload["control_system_id"],
        version_number=payload["version_number"],
        created_at=payload["created_at"],
        topology=Topology(nodes=nodes, edges=edges),
        policies=LoopPolicy.model_validate(payload["policies"]),
        metadata=payload.get("metadata") or {},
    )


def _decode_node(payload: dict[str, Any]) -> Node:
    data = _strip_type(payload)
    binding = data.get("capability_binding")
    if isinstance(binding, dict):
        data["capability_binding"] = CapabilityRef(**_strip_type(binding))
    data["input_ports"] = tuple(_decode_port(p) for p in data.get("input_ports") or ())
    data["output_ports"] = tuple(_decode_port(p) for p in data.get("output_ports") or ())
    return Node(**data)


def _decode_port(payload: dict[str, Any]) -> Port:
    data = _strip_type(payload)
    kind = data["signal_kind"]
    if isinstance(kind, dict):
        data["signal_kind"] = _KIND_BY_NAME[kind["name"]]
    elif isinstance(kind, str):
        data["signal_kind"] = _KIND_BY_NAME[kind]
    return Port(**data)


def _strip_type(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "__type__"}
