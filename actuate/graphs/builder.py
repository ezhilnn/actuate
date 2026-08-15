"""Fluent graph construction for the PyPI library (nodes, edges, custom agents)."""

from __future__ import annotations

from typing import Any

from actuate.graphs.catalog import agent_by_id, register_agent


def agent(
    ident: str,
    *,
    kind: str = "agent",
    title: str | None = None,
    system: str = "",
    color: str = "#3d8bfd",
    blurb: str = "Custom agent",
) -> str:
    """Register a custom specialist and return its id for Graph.add()."""
    register_agent(
        {
            "id": ident,
            "kind": kind,
            "title": title or ident,
            "system": system,
            "color": color,
            "blurb": blurb,
        }
    )
    return ident


class Agents:
    """Built-in agent ids for Graph.add(node_id, Agents.researcher)."""

    ingress = "ingress"
    egress = "egress"
    researcher = "researcher"
    fact_checker = "fact_checker"
    summarizer = "summarizer"
    explainer = "explainer"
    editor = "editor"
    critic = "critic"
    synthesizer = "synthesizer"
    planner = "planner"
    data_analyst = "data_analyst"
    judge_accuracy = "judge_accuracy"
    judge_safety = "judge_safety"
    judge_clarity = "judge_clarity"
    judge_complete = "judge_complete"


class Graph:
    """User-facing DAG: add nodes and edges the same way as the designer canvas."""

    def __init__(
        self,
        name: str = "graph",
        *,
        graph_id: str | None = None,
        target_score: float = 0.85,
        max_passes: int = 4,
        blurb: str = "",
    ) -> None:
        self.id = graph_id or name
        self.name = name
        self.blurb = blurb or "Library graph"
        self.target_score = float(target_score)
        self.max_passes = int(max_passes)
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, str]] = []
        self._col = 0

    def add(
        self,
        node_id: str,
        agent_id: str | dict[str, Any],
        *,
        x: float | None = None,
        y: float | None = None,
        label: str | None = None,
        system: str | None = None,
    ) -> Graph:
        if isinstance(agent_id, dict):
            spec = register_agent(agent_id)
            aid = str(spec["id"])
        else:
            aid = str(agent_id)
            spec = agent_by_id(aid)
        if node_id in self._nodes:
            raise ValueError(f"node '{node_id}' already exists")
        idx = len(self._nodes)
        self._nodes[node_id] = {
            "id": node_id,
            "agent": aid,
            "x": float(x if x is not None else (idx % 6) * 220),
            "y": float(y if y is not None else (idx // 6) * 120),
            "label": label or str(spec.get("title") or aid),
            "kind": str(spec.get("kind") or "agent"),
            "system": system if system is not None else str(spec.get("system") or ""),
        }
        return self

    def add_node(self, node_id: str, agent_id: str | dict[str, Any], **kwargs: Any) -> Graph:
        return self.add(node_id, agent_id, **kwargs)

    def edge(self, source: str, target: str, *, edge_id: str | None = None) -> Graph:
        if source not in self._nodes:
            raise KeyError(f"unknown source node '{source}'")
        if target not in self._nodes:
            raise KeyError(f"unknown target node '{target}'")
        if source == target:
            raise ValueError("cannot connect a node to itself")
        eid = edge_id or f"e-{source}-{target}"
        if any(e["id"] == eid or (e["source"] == source and e["target"] == target) for e in self._edges):
            return self
        self._edges.append({"id": eid, "source": source, "target": target})
        return self

    def add_edge(self, source: str, target: str, **kwargs: Any) -> Graph:
        return self.edge(source, target, **kwargs)

    def connect(self, *node_ids: str) -> Graph:
        """Wire a path: connect('in', 'writer', 'judge', 'out')."""
        if len(node_ids) < 2:
            raise ValueError("connect needs at least two node ids")
        for src, tgt in zip(node_ids, node_ids[1:]):
            self.edge(src, tgt)
        return self

    def validate(self) -> None:
        from actuate.graphs.runner import topological_order

        topological_order(list(self._nodes.values()), self._edges)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "name": self.name,
            "blurb": self.blurb,
            "target_score": self.target_score,
            "max_passes": self.max_passes,
            "nodes": list(self._nodes.values()),
            "edges": list(self._edges),
        }


def as_graph_dict(graph: Graph | dict[str, Any]) -> dict[str, Any]:
    if isinstance(graph, Graph):
        return graph.to_dict()
    if hasattr(graph, "to_dict"):
        return dict(graph.to_dict())  # type: ignore[no-any-return]
    return dict(graph)
