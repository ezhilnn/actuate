"""actuate.domain.execution_session — active execution vs. history.

A `Run` (run.py) is the persisted, historical record — an identity plus
whatever `EventLog` a `RunStore` has durably accepted. `ExecutionSession`
is the *active*, in-memory counterpart the `ExecutionEngine` actually
mutates while a Run is in progress: pending signals waiting to be
consumed off an edge, the current iteration cursor, and an unflushed
event buffer.

This separation (review 2, point 3) is what makes recovery/replay/future
distributed execution clean: a crashed session can be reconstructed by
loading the last persisted Run's EventLog from a RunStore and resuming
an ExecutionSession from it, instead of a Run itself needing to carry
mutable execution-cursor state that has no meaning once persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from actuate.domain.events import Event, EventLog
from actuate.domain.run import Run, RunMode
from actuate.domain.signals import Signal


@dataclass(slots=True)
class ExecutionSession:
    run_id: str
    specification_id: str
    mode: RunMode = "live"
    iteration_index: int = 0
    pending_signals: dict[tuple[str, str], Signal] = field(default_factory=dict)
    _event_buffer: list[Event] = field(default_factory=list)

    def emit(self, event: Event) -> None:
        self._event_buffer.append(event)

    def deposit(self, node_id: str, port_name: str, signal: Signal) -> None:
        self.pending_signals[(node_id, port_name)] = signal

    def take(self, node_id: str, port_name: str) -> Signal | None:
        return self.pending_signals.pop((node_id, port_name), None)

    def flush(self) -> list[Event]:
        """Drain the buffer for a RunStore to persist. Callers own
        actually writing these out — this class performs no I/O itself.
        """
        drained = self._event_buffer
        self._event_buffer = []
        return drained

    def snapshot(self) -> Run:
        """A read-only Run view of everything buffered so far, for
        callers that want to use the Run projections (domain.run) before
        a flush completes.
        """
        return Run(
            id=self.run_id,
            specification_id=self.specification_id,
            mode=self.mode,
            events=EventLog(list(self._event_buffer)),
        )
