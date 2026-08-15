"""actuate.domain.events — immutable facts about execution.

Signals (signals.py) are data on a wire; Events are facts about what
happened, appended to a Run's `EventLog`. The distinction is load-bearing
(see the frozen architecture doc, §3.4/§9): Signals are never mutated,
Events are never rewritten. Every runtime view — current status,
iteration count, metrics, convergence progress — is a *projection*
computed by scanning `EventLog`, never independently stored mutable
state (see `domain.run`).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TypeVar

from actuate.domain.signals import Signal


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Base class for every event kind. Never instantiated directly."""

    id: str = field(default_factory=_new_id)
    run_id: str
    at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunStarted(Event):
    specification_id: str
    mode: str  # "live" | "simulated" | "replay"


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeExecutionStarted(Event):
    node_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeExecutionCompleted(Event):
    node_id: str
    produced_signal_ids: tuple[str, ...] = ()
    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class SignalEmitted(Event):
    """The only place a Signal's full value is durably captured."""

    signal: Signal


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedbackPathEntered(Event):
    """Marks the start of one traversal of the mandatory feedback path.
    `Iteration` (domain.run) is derived by scanning for these.
    """

    iteration_index: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RunStatusChanged(Event):
    from_status: str
    to_status: str
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class RunFailed(Event):
    node_id: str | None
    error: str


EventT = TypeVar("EventT", bound=Event)


class EventLog:
    """Append-only. No method exists to remove or replace an entry —
    that's the entire enforcement mechanism, deliberately simple.
    """

    __slots__ = ("_events",)

    def __init__(self, events: Iterable[Event] | None = None) -> None:
        self._events: list[Event] = list(events) if events else []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def of_kind(self, event_type: type[EventT]) -> list[EventT]:
        return [e for e in self._events if isinstance(e, event_type)]

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, index: int) -> Event:
        return self._events[index]
