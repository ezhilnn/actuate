"""actuate.telemetry.mlflow_sink — optional MLflow experiment logging.

`mlflow` is imported lazily so this module is never required unless
`MLflowEventSink` is actually instantiated. Buffers each Run's Events
in-memory (mirroring `TracingEventSink`'s per-run span tracking) and
logs one MLflow run when a terminal `RunStatusChanged` arrives, using
the same `domain.run` projections (`metrics`, `current_status`) every
other consumer of a Run uses — no separate collection mechanism.
"""

from __future__ import annotations

from typing import Any

from actuate.domain.events import Event, EventLog, RunStarted, RunStatusChanged
from actuate.domain.run import Run, metrics

_TERMINAL_STATUSES = frozenset(
    {"converged", "exhausted", "timed_out", "oscillating", "failed", "aborted"}
)


class MLflowEventSink:
    def __init__(self, *, experiment_name: str = "actuate", tracking_uri: str | None = None) -> None:
        try:
            import mlflow
        except ImportError as exc:
            raise ImportError(
                "MLflowEventSink requires mlflow: pip install 'actuate[telemetry]'"
            ) from exc

        self._mlflow: Any = mlflow
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self._buffers: dict[str, EventLog] = {}
        self._specification_ids: dict[str, str] = {}

    async def handle(self, event: Event) -> None:
        buffer = self._buffers.setdefault(event.run_id, EventLog())
        buffer.append(event)

        if isinstance(event, RunStarted):
            self._specification_ids[event.run_id] = event.specification_id
            return

        if isinstance(event, RunStatusChanged) and event.to_status in _TERMINAL_STATUSES:
            run = Run(
                id=event.run_id,
                specification_id=self._specification_ids.get(event.run_id, ""),
                events=buffer,
            )
            summary = metrics(run)
            with self._mlflow.start_run(run_name=event.run_id):
                self._mlflow.log_param("status", event.to_status)
                self._mlflow.log_param("specification_id", run.specification_id)
                self._mlflow.log_metric("iterations", summary.iteration_count)
                self._mlflow.log_metric("total_latency_seconds", summary.total_latency_seconds)
                self._mlflow.log_metric("total_tokens", summary.total_tokens)
                if summary.best_score is not None:
                    self._mlflow.log_metric("best_score", summary.best_score)
            del self._buffers[event.run_id]
            self._specification_ids.pop(event.run_id, None)
