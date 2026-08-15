"""actuate.telemetry.otel — tracer setup.

`get_tracer()` never raises: if `opentelemetry-api` isn't installed, it
returns an in-house no-op tracer with the same interface, so
`TracingEventSink` works identically whether or not OpenTelemetry is
present. Call `configure_otlp_exporter()` separately to actually ship
spans somewhere (requires `opentelemetry-sdk` + the OTLP exporter).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Literal


class _NullSpan(AbstractContextManager["_NullSpan"]):
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> _NullSpan:  # noqa: PYI034 - typing.Self needs Python 3.11+
        return self

    def __exit__(self, *exc_info: object) -> Literal[False]:
        return False


class _NullTracer:
    def start_span(self, name: str, **kwargs: Any) -> _NullSpan:
        return _NullSpan()

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NullSpan:
        return _NullSpan()


def get_tracer(name: str = "actuate") -> Any:
    try:
        from opentelemetry import trace
    except ImportError:
        return _NullTracer()
    return trace.get_tracer(name)


def configure_otlp_exporter(*, endpoint: str | None = None, service_name: str = "actuate") -> None:
    """Wires the global TracerProvider to export spans via OTLP. Requires
    `opentelemetry-sdk` + `opentelemetry-exporter-otlp`
    (`pip install "actuate[telemetry]"`).
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise ImportError(
            "configure_otlp_exporter requires opentelemetry-sdk and "
            "opentelemetry-exporter-otlp: pip install 'actuate[telemetry]'"
        ) from exc

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
