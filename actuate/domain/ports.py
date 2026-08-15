"""actuate.domain.ports — typed connection points on a Node.

Signals travel port-to-port, never node-to-node directly. An `Edge` is
only valid (see `topology.py`) when its source port's `signal_kind`
matches its destination port's `signal_kind`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from actuate.domain.signals import Signal

Direction = Literal["in", "out"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Port:
    name: str
    signal_kind: type[Signal]
    direction: Direction


@dataclass(frozen=True, slots=True, kw_only=True)
class Edge:
    from_node: str
    from_port: str
    to_node: str
    to_port: str
