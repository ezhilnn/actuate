"""Standard closed-loop topology: plant → sensors → merge → controller → actuator.

This graph is the default control system a user is building. Extra nodes
(memory, tools, routers) can be added later without changing the engine
contract for the common case.
"""

from __future__ import annotations

from actuate.domain.capability import CapabilityKinds, CapabilityRef
from actuate.domain.nodes import Node, NodeKinds
from actuate.domain.ports import Edge, Port
from actuate.domain.signals import ControlSignal, ErrorSignal, ObservationSignal, OutputSignal, PromptSignal
from actuate.domain.topology import Topology


def standard_closed_loop(
    *,
    plant_name: str = "litellm",
    plant_params: dict[str, object] | None = None,
    sensor_name: str = "rule",
    sensor_params: dict[str, object] | None = None,
    actuator_name: str = "prompt",
    actuator_params: dict[str, object] | None = None,
    fusion_name: str = "single",
    controller_name: str = "rule",
) -> Topology:
    plant = Node(
        id="plant",
        kind=NodeKinds.PLANT,
        input_ports=(Port(name="prompt", signal_kind=PromptSignal, direction="in"),),
        output_ports=(Port(name="output", signal_kind=OutputSignal, direction="out"),),
        capability_binding=CapabilityRef(
            kind=CapabilityKinds.PLANT, name=plant_name, params=dict(plant_params or {})
        ),
    )
    sensor = Node(
        id="sensor",
        kind=NodeKinds.SENSOR,
        input_ports=(Port(name="output", signal_kind=OutputSignal, direction="in"),),
        output_ports=(Port(name="observation", signal_kind=ObservationSignal, direction="out"),),
        capability_binding=CapabilityRef(
            kind=CapabilityKinds.SENSOR, name=sensor_name, params=dict(sensor_params or {})
        ),
    )
    merge = Node(
        id="merge",
        kind=NodeKinds.MERGE,
        input_ports=(Port(name="observation", signal_kind=ObservationSignal, direction="in"),),
        output_ports=(Port(name="error", signal_kind=ErrorSignal, direction="out"),),
        capability_binding=CapabilityRef(kind=CapabilityKinds.SIGNAL_FUSION_STRATEGY, name=fusion_name),
    )
    controller = Node(
        id="controller",
        kind=NodeKinds.CONTROLLER,
        input_ports=(Port(name="error", signal_kind=ErrorSignal, direction="in"),),
        output_ports=(Port(name="decision", signal_kind=ControlSignal, direction="out"),),
        capability_binding=CapabilityRef(kind=CapabilityKinds.CONTROLLER, name=controller_name),
    )
    actuator = Node(
        id="actuator",
        kind=NodeKinds.ACTUATOR,
        input_ports=(Port(name="decision", signal_kind=ControlSignal, direction="in"),),
        output_ports=(Port(name="prompt_mutation", signal_kind=ControlSignal, direction="out"),),
        capability_binding=CapabilityRef(
            kind=CapabilityKinds.ACTUATOR, name=actuator_name, params=dict(actuator_params or {})
        ),
    )
    return Topology(
        nodes=(plant, sensor, merge, controller, actuator),
        edges=(
            Edge(from_node="plant", from_port="output", to_node="sensor", to_port="output"),
            Edge(from_node="sensor", from_port="observation", to_node="merge", to_port="observation"),
            Edge(from_node="merge", from_port="error", to_node="controller", to_port="error"),
            Edge(from_node="controller", from_port="decision", to_node="actuator", to_port="decision"),
        ),
    )
