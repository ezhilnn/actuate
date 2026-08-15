"""actuate.domain.topology — pure structure. Zero runtime state.

A `Topology` describes nodes, edges, ports, and routing — nothing about
execution. Validation happens once, when a `Specification` is created,
never at Run time (see `domain.specification`).

Per the frozen architecture (§1, revised): whether a `Topology` must
contain a feedback path (a `plant` node's output structurally reaching
an `actuator` node, through `sensor`/`merge`/etc.) is governed by a
pluggable `TopologyValidationPolicy`, defaulting to `RequireFeedbackPath`
— strict-by-default, but a deliberate, named escape hatch for legitimate
edge cases (single-shot Plant+Sensor testing during authoring,
evaluation-only `benchmark` fragments) instead of forcing awkward
synthetic self-loop edges just to pass validation. The reverse hop (an
actuator's `ControlSignal` becoming the next iteration's `PromptSignal`)
is never a literal Topology edge — see `RequireFeedbackPath`'s docstring
below for why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from actuate.domain.exceptions import PortMismatchError, TopologyValidationError
from actuate.domain.nodes import Node, NodeKinds
from actuate.domain.ports import Edge


@dataclass(frozen=True, slots=True, kw_only=True)
class Topology:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(f"Unknown node id '{node_id}'.")

    def outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.from_node == node_id]

    def incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.to_node == node_id]

    def validate(self, *, feedback_policy: TopologyValidationPolicy | None = None) -> None:
        _validate_structure(self)
        (feedback_policy or RequireFeedbackPath()).check(self)


def _validate_structure(topology: Topology) -> None:
    ids = [n.id for n in topology.nodes]
    if len(ids) != len(set(ids)):
        raise TopologyValidationError("Duplicate node ids in Topology.")

    for edge in topology.edges:
        for node_id in (edge.from_node, edge.to_node):
            if node_id not in ids:
                raise TopologyValidationError(
                    f"Edge references unknown node '{node_id}'."
                )
        source = topology.node(edge.from_node).output_port(edge.from_port)
        target = topology.node(edge.to_node).input_port(edge.to_port)
        if source.signal_kind is not target.signal_kind:
            raise PortMismatchError(
                f"{edge.from_node}.{edge.from_port} ({source.signal_kind.__name__}) -> "
                f"{edge.to_node}.{edge.to_port} ({target.signal_kind.__name__}) "
                "connects incompatible signal kinds."
            )


@runtime_checkable
class TopologyValidationPolicy(Protocol):
    """Capability kind: `topology_validation_policy`. Pure structural
    check over a `Topology` — no execution-time information available.
    """

    def check(self, topology: Topology) -> None: ...


class RequireFeedbackPath:
    """Default, strict policy: rejects any Topology where no `actuator`
    node is reachable via forward edges from a `plant` node (through
    `sensor`/`merge`/etc.) — i.e. no actuator's decision is structurally
    informed by that plant's output. The reverse hop (an actuator's
    correction becoming the *next* iteration's prompt) is deliberately
    **not** a literal Topology edge: a `ControlSignal` and a `PromptSignal`
    are different signal kinds by design (see `domain.signals`), and
    that translation — draining a `ControlSignal` and depositing a fresh
    `PromptSignal` for the next iteration — is the `ExecutionEngine`'s
    own mandatory feedback mechanism at the iteration boundary, not
    something a Topology author wires up by hand. This is what keeps
    Actuate from silently becoming a generic acyclic pipeline/workflow
    tool — see the frozen architecture, §1.
    """

    def check(self, topology: Topology) -> None:
        plant_ids = {n.id for n in topology.nodes if n.kind == NodeKinds.PLANT}
        actuator_ids = {n.id for n in topology.nodes if n.kind == NodeKinds.ACTUATOR}
        if not plant_ids or not actuator_ids:
            raise TopologyValidationError(
                "Topology has no feedback path: at least one 'plant' node and "
                "one 'actuator' node are required."
            )

        adjacency: dict[str, list[str]] = {}
        for edge in topology.edges:
            adjacency.setdefault(edge.from_node, []).append(edge.to_node)

        for plant_id in plant_ids:
            if _can_reach(plant_id, actuator_ids, adjacency):
                return

        raise TopologyValidationError(
            "Topology has no feedback path: no plant node's output reaches "
            "any actuator node. Use a permissive TopologyValidationPolicy "
            "explicitly if a feedback-free topology is genuinely intended."
        )


class AllowAnyTopology:
    """The explicit escape hatch: no feedback-path requirement at all.
    Intended for authoring-time fragments (single-shot Plant+Sensor
    testing) and evaluation-only `benchmark` topologies — must be opted
    into by name, never the default.
    """

    def check(self, topology: Topology) -> None:
        return None


def _can_reach(start: str, targets: set[str], adjacency: dict[str, list[str]]) -> bool:
    visited: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in targets:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, []))
    return False
