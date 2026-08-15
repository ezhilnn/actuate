"""actuate.telemetry — Phase C: EventSink implementations.

Public API:

    from actuate.telemetry import (
        get_tracer, configure_otlp_exporter,
        TracingEventSink, PersistenceEventSink, MLflowEventSink,
        to_dataframe, summarize, load_run,
    )

Every implementation here satisfies `domain.protocols.EventSink`
(one method, `handle(event)`) and is registered with an
`ExecutionEngine` via its `event_sinks=[...]` constructor argument —
independent subscribers to the same Event stream, no stacking order to
get right.
"""

from actuate.telemetry.mlflow_sink import MLflowEventSink
from actuate.telemetry.otel import configure_otlp_exporter, get_tracer
from actuate.telemetry.persistence_sink import PersistenceEventSink
from actuate.telemetry.reports import load_run, summarize, to_dataframe
from actuate.telemetry.tracing import TracingEventSink

__all__ = [
    "MLflowEventSink",
    "PersistenceEventSink",
    "TracingEventSink",
    "configure_otlp_exporter",
    "get_tracer",
    "load_run",
    "summarize",
    "to_dataframe",
]
