"""actuate.domain.run — Runtime. `Run` owns nothing but an `EventLog`;
every other view (status, iterations, metrics, convergence progress) is
a projection — a pure function over that log, never independently
stored mutable state. This is the "take event-sourcing to its logical
conclusion" resolution from the frozen architecture review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeVar

from actuate.domain.events import (
    Event,
    EventLog,
    FeedbackPathEntered,
    RunFailed,
    RunStarted,
    RunStatusChanged,
    SignalEmitted,
)
from actuate.domain.signals import (
    ControlSignal,
    ErrorSignal,
    ObservationSignal,
    OutputSignal,
    PromptSignal,
    Signal,
    TokenUsage,
)

RunMode = Literal["live", "simulated", "replay"]
RunStatus = Literal[
    "pending",
    "running",
    "converged",
    "exhausted",
    "timed_out",
    "oscillating",
    "failed",
    "aborted",
]

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"converged", "exhausted", "timed_out", "oscillating", "failed", "aborted"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    id: str
    specification_id: str
    mode: RunMode = "live"
    events: EventLog = field(default_factory=EventLog)


# --------------------------------------------------------------------
# Projections — pure functions over Run.events. Nothing below this line
# is stored; everything is recomputed from the EventLog on every call.
# --------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class IterationView:
    index: int
    prompt: PromptSignal | None
    output: OutputSignal | None
    observations: tuple[ObservationSignal, ...]
    error_signal: ErrorSignal | None
    control_signal: ControlSignal | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RunMetricsView:
    iteration_count: int
    total_latency_seconds: float
    total_tokens: int
    best_score: float | None


def current_status(run: Run) -> RunStatus:
    changes = run.events.of_kind(RunStatusChanged)
    if changes:
        return changes[-1].to_status  # type: ignore[return-value]
    return "pending"


def started_at(run: Run) -> float | None:
    starts = run.events.of_kind(RunStarted)
    return starts[0].at if starts else None


def ended_at(run: Run) -> float | None:
    if current_status(run) not in _TERMINAL_STATUSES:
        return None
    return run.events[-1].at if len(run.events) else None


def failure_reason(run: Run) -> str | None:
    failures = run.events.of_kind(RunFailed)
    return failures[-1].error if failures else None


_SignalT = TypeVar("_SignalT", bound=Signal)


def _last_of(signals: list[Signal], kind: type[_SignalT]) -> _SignalT | None:
    matches = [s for s in signals if isinstance(s, kind)]
    return matches[-1] if matches else None


def iterations(run: Run) -> list[IterationView]:
    boundaries = run.events.of_kind(FeedbackPathEntered)
    if not boundaries:
        return []

    views: list[IterationView] = []
    for idx, boundary in enumerate(boundaries):
        window_start = boundary.at
        window_end = boundaries[idx + 1].at if idx + 1 < len(boundaries) else float("inf")
        signals: list[Signal] = [
            e.signal
            for e in run.events.of_kind(SignalEmitted)
            if window_start <= e.at < window_end
        ]
        views.append(
            IterationView(
                index=boundary.iteration_index,
                prompt=_last_of(signals, PromptSignal),
                output=_last_of(signals, OutputSignal),
                observations=tuple(s for s in signals if isinstance(s, ObservationSignal)),
                error_signal=_last_of(signals, ErrorSignal),
                control_signal=_last_of(signals, ControlSignal),
            )
        )
    return views


def metrics(run: Run) -> RunMetricsView:
    views = iterations(run)
    total_latency = 0.0
    total_tokens = 0
    best_score: float | None = None
    for view in views:
        if view.output is not None:
            total_latency += view.output.latency_seconds
            usage: TokenUsage = view.output.usage
            total_tokens += usage.total_tokens
        for obs in view.observations:
            if best_score is None or obs.score > best_score:
                best_score = obs.score
    return RunMetricsView(
        iteration_count=len(views),
        total_latency_seconds=total_latency,
        total_tokens=total_tokens,
        best_score=best_score,
    )


def convergence_progress(run: Run) -> float | None:
    for view in reversed(iterations(run)):
        if view.error_signal is not None:
            return view.error_signal.measured
    return None


def all_events(run: Run) -> list[Event]:
    return list(run.events)
