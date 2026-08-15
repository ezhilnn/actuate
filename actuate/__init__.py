"""Actuate — closed-loop control graphs for generation, validation, and reward.

Library usage:

    from actuate import Graph, Agents, GraphRunner, GraphEnv, agent
"""

from actuate.graphs.builder import Agents, Graph, agent
from actuate.graphs.catalog import list_agents, register_agent
from actuate.graphs.report import pass_report, run_payload
from actuate.graphs.runner import GraphRunner
from actuate.graphs.templates import templates
from actuate.graphs.training import GraphEnv, Trajectory, dpo_pairs, trajectories_from_run

__version__ = "0.1.0"

__all__ = [
    "Agents",
    "Graph",
    "GraphEnv",
    "GraphRunner",
    "Trajectory",
    "agent",
    "dpo_pairs",
    "list_agents",
    "pass_report",
    "register_agent",
    "run_payload",
    "templates",
    "trajectories_from_run",
    "__version__",
]
