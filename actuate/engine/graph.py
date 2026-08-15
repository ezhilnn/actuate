"""Optional NetworkX helpers for the control-system graph (designer + validation)."""

from __future__ import annotations

from typing import Any

from actuate.domain.nodes import NodeKinds
from actuate.domain.topology import Topology


def topology_as_dict(topology: Topology) -> dict[str, Any]:
    try:
        import networkx as nx
    except ImportError:
        return {
            "nodes": [n.id for n in topology.nodes],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in topology.edges],
            "backend": "adjacency",
        }

    graph = nx.DiGraph()
    for node in topology.nodes:
        graph.add_node(node.id, kind=node.kind)
    for edge in topology.edges:
        graph.add_edge(edge.from_node, edge.to_node, from_port=edge.from_port, to_port=edge.to_port)

    plants = [n.id for n in topology.nodes if n.kind == NodeKinds.PLANT]
    actuators = [n.id for n in topology.nodes if n.kind == NodeKinds.ACTUATOR]
    paths: list[list[str]] = []
    for plant in plants:
        for actuator in actuators:
            if nx.has_path(graph, plant, actuator):
                paths.append(nx.shortest_path(graph, plant, actuator))

    return {
        "nodes": [{"id": n, **graph.nodes[n]} for n in graph.nodes],
        "edges": [{"from": u, "to": v, **graph.edges[u, v]} for u, v in graph.edges],
        "feedback_paths": paths,
        "is_dag": nx.is_directed_acyclic_graph(graph),
        "backend": "networkx",
    }
