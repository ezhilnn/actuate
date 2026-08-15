"""actuate.domain.nodes — the generic execution node.

One runtime shape for every kind of node in a Topology. `kind` is an
open string (like `CapabilityKind`) so plugins can introduce new node
kinds without a core change; the kinds Actuate ships with are listed in
`NodeKinds`. A node's `capability_binding` says which registered
capability instance implements it — the node itself carries no behavior,
only structure (id, ports, and that binding).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from actuate.domain.capability import CapabilityRef
from actuate.domain.ports import Port

NodeKind = str


class NodeKinds:
    """String constants for the node kinds Actuate ships with. Not
    exhaustive by design — a `plugin`-kind node may bind any third-party
    capability, and third parties may introduce further kinds entirely.
    """

    PLANT = "plant"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    ACTUATOR = "actuator"
    MERGE = "merge"
    ROUTER = "router"
    DECISION = "decision"
    MEMORY = "memory"
    TOOL = "tool"
    HUMAN_APPROVAL = "human_approval"
    BENCHMARK = "benchmark"
    PARALLEL = "parallel"
    DELAY = "delay"
    PLUGIN = "plugin"


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    id: str
    kind: NodeKind
    input_ports: tuple[Port, ...] = ()
    output_ports: tuple[Port, ...] = ()
    capability_binding: CapabilityRef | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def output_port(self, name: str) -> Port:
        for port in self.output_ports:
            if port.name == name:
                return port
        raise KeyError(f"Node '{self.id}' has no output port named '{name}'.")

    def input_port(self, name: str) -> Port:
        for port in self.input_ports:
            if port.name == name:
                return port
        raise KeyError(f"Node '{self.id}' has no input port named '{name}'.")
