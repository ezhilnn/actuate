"""actuate.domain.specification — the immutable, versioned definition.

A `Specification` is what a `Run` actually references — never a mutable
`ControlSystem` directly — which is what makes "run #4821 used exactly
this configuration" an answerable question. Validated once, at creation
time (`create_specification`), never at Run time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from actuate.domain.policy import LoopPolicy, SetPoint
from actuate.domain.topology import Topology, TopologyValidationPolicy


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True, kw_only=True)
class Specification:
    id: str = field(default_factory=_new_id)
    control_system_id: str
    version_number: int
    created_at: float = field(default_factory=time.time)
    topology: Topology
    policies: LoopPolicy
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def objective(self) -> SetPoint:
        return self.policies.set_point


def create_specification(
    *,
    control_system_id: str,
    version_number: int,
    topology: Topology,
    policies: LoopPolicy | None = None,
    metadata: dict[str, Any] | None = None,
    feedback_policy: TopologyValidationPolicy | None = None,
) -> Specification:
    """The only sanctioned way to construct a Specification — always
    validates the Topology first, so an invalid Specification can never
    be persisted or referenced by a Run.
    """
    topology.validate(feedback_policy=feedback_policy)
    return Specification(
        control_system_id=control_system_id,
        version_number=version_number,
        topology=topology,
        policies=policies or LoopPolicy(),
        metadata=metadata or {},
    )
