"""actuate.telemetry.persistence_sink — the durability EventSink.

Thin by design: durability is "write every Event to a RunStore," nothing
more. All the actual persistence logic (schema, transactions, backend
choice) lives behind the `RunStore` Protocol — this class has no opinion
on which implementation is bound (`InMemoryRunStore` today,
`SqlRunStore` in Phase D).
"""

from __future__ import annotations

from actuate.domain.events import Event
from actuate.domain.protocols import RunStore


class PersistenceEventSink:
    def __init__(self, run_store: RunStore) -> None:
        self.run_store = run_store

    async def handle(self, event: Event) -> None:
        await self.run_store.append_event(event)
