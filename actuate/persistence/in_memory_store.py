"""actuate.persistence.in_memory_store — the zero-dependency default
`RunStore`. `SqlRunStore` (PostgreSQL/MySQL via SQLAlchemy, per the
frozen architecture) lands in Phase D; this exists now so
`PersistenceEventSink` (telemetry/) and the ExecutionEngine have
something real to write to without requiring a database — matching the
"the engine must run with zero DB" principle already established for
the domain layer.
"""

from __future__ import annotations

from actuate.domain.control_system import ControlSystem, Workspace
from actuate.domain.events import Event, EventLog
from actuate.domain.specification import Specification


class InMemoryRunStore:
    def __init__(self) -> None:
        self._events: dict[str, EventLog] = {}
        self._specifications: dict[str, Specification] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._control_systems: dict[str, ControlSystem] = {}
        self._keys: dict[str, str] = {}

    async def append_event(self, event: Event) -> None:
        self._events.setdefault(event.run_id, EventLog()).append(event)

    async def load_events(self, run_id: str) -> list[Event]:
        return list(self._events.get(run_id, EventLog()))

    async def save_specification(self, specification: Specification) -> None:
        self._specifications[specification.id] = specification

    async def load_specification(self, specification_id: str) -> Specification:
        return self._specifications[specification_id]

    async def list_specification_ids(self) -> list[str]:
        return list(self._specifications)

    async def list_run_ids(self) -> list[str]:
        return list(self._events)

    def known_run_ids(self) -> list[str]:
        return list(self._events)

    async def save_workspace(self, workspace: Workspace) -> None:
        self._workspaces[workspace.id] = workspace

    async def list_workspaces(self) -> list[Workspace]:
        return list(self._workspaces.values())

    async def save_control_system(self, control_system: ControlSystem) -> None:
        self._control_systems[control_system.id] = control_system

    async def list_control_systems(self, workspace_id: str | None = None) -> list[ControlSystem]:
        systems = list(self._control_systems.values())
        if workspace_id is not None:
            systems = [s for s in systems if s.workspace_id == workspace_id]
        return systems

    async def put_key(self, provider: str, api_key: str) -> None:
        self._keys[provider] = api_key

    async def get_keys(self) -> dict[str, str]:
        return dict(self._keys)
