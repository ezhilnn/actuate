"""actuate.domain.control_system — stable identity, above Specification.

`ControlSystem` is the aggregate root a user names and iterates on.
`Specification` (specification.py) is the immutable, versioned payload;
a `ControlSystem` has many Specifications over time, referenced by
`control_system_id`, not embedded here — avoids one mutable object
owning a collection of the very things meant to be immutable snapshots.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True, kw_only=True)
class Workspace:
    id: str = field(default_factory=_new_id)
    name: str
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlSystem:
    id: str = field(default_factory=_new_id)
    workspace_id: str
    name: str
    description: str = ""
    created_at: float = field(default_factory=time.time)
