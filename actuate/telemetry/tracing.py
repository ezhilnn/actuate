"""actuate.telemetry.tracing — TracingEventSink.

One `EventSink` implementation among several (PersistenceEventSink,
MLflowEventSink) that all subscribe to the same Event stream — this is
the frozen architecture's telemetry-unification resolution: no more
per-concern wrapper classes stacked in a caller-chosen order, just
independent subscribers to `ExecutionEngine`'s event fan-out.

v1 keeps one span per Run (opened on `RunStarted`, closed on a terminal
`RunStatusChanged`/`RunFailed`); node executions and signal emissions
are recorded as *events* on that span rather than a full nested
span-per-node hierarchy — enough for prompt/output/score timelines and
exception traces without the added complexity of manual OTel context
propagation across an event-driven (not call-stack-driven) callback.
"""

from __future__ import annotations

from typing import Any

from actuate.domain.events import (
    Event,
    FeedbackPathEntered,
    NodeExecutionCompleted,
    NodeExecutionStarted,
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
)
from actuate.telemetry.otel import get_tracer

_TERMINAL_STATUSES = frozenset(
    {"converged", "exhausted", "timed_out", "oscillating", "failed", "aborted"}
)


class TracingEventSink:
    def __init__(self, *, tracer: Any = None) -> None:
        self.tracer = tracer or get_tracer()
        self._spans: dict[str, Any] = {}

    async def handle(self, event: Event) -> None:
        if isinstance(event, RunStarted):
            span = self.tracer.start_span("actuate.run")
            span.set_attribute("actuate.run_id", event.run_id)
            span.set_attribute("actuate.specification_id", event.specification_id)
            span.set_attribute("actuate.mode", event.mode)
            self._spans[event.run_id] = span
            return

        span = self._spans.get(event.run_id)
        if span is None:
            return

        if isinstance(event, FeedbackPathEntered):
            span.add_event("iteration_started", {"iteration_index": event.iteration_index})
        elif isinstance(event, NodeExecutionStarted):
            span.add_event("node_execution_started", {"node_id": event.node_id})
        elif isinstance(event, NodeExecutionCompleted):
            span.add_event(
                "node_execution_completed",
                {"node_id": event.node_id, "duration_seconds": event.duration_seconds},
            )
        elif isinstance(event, SignalEmitted):
            span.add_event(f"signal:{type(event.signal).__name__}", _signal_attributes(event.signal))
        elif isinstance(event, RunFailed):
            span.set_attribute("actuate.error", event.error)
            span.record_exception(RuntimeError(event.error))
        elif isinstance(event, RunStatusChanged):
            span.set_attribute("actuate.status", event.to_status)
            if event.to_status in _TERMINAL_STATUSES:
                span.end()
                del self._spans[event.run_id]


def _signal_attributes(signal: Signal) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "signal_id": signal.id,
        "produced_by_node": signal.produced_by_node,
        "produced_by_port": signal.produced_by_port,
    }
    if isinstance(signal, (PromptSignal, OutputSignal)):
        attrs["text_length"] = len(signal.text)
    if isinstance(signal, ObservationSignal):
        attrs["score"] = signal.score
        attrs["passed"] = signal.passed
    if isinstance(signal, ErrorSignal):
        attrs["setpoint"] = signal.setpoint
        attrs["measured"] = signal.measured
        attrs["within_tolerance"] = signal.within_tolerance
    if isinstance(signal, ControlSignal):
        attrs["action_kind"] = signal.action_kind
    return attrs
