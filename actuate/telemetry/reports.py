"""actuate.telemetry.reports — pandas reporting over persisted Runs.

Reads `Run`s back out via `RunStore` + the `domain.run` projections —
there is no separate collection mechanism to keep in sync, unlike
LoopForge v1's `MetricsCollector`/`RunMetrics`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from actuate.domain.events import EventLog
from actuate.domain.protocols import RunStore
from actuate.domain.run import Run, current_status, metrics


async def load_run(run_store: RunStore, run_id: str, *, specification_id: str = "") -> Run:
    events = await run_store.load_events(run_id)
    return Run(id=run_id, specification_id=specification_id, events=EventLog(events))


def to_dataframe(runs: list[Run]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for run in runs:
        summary = metrics(run)
        rows.append(
            {
                "run_id": run.id,
                "specification_id": run.specification_id,
                "status": current_status(run),
                "iterations": summary.iteration_count,
                "total_latency_seconds": summary.total_latency_seconds,
                "total_tokens": summary.total_tokens,
                "best_score": summary.best_score,
            }
        )
    df: pd.DataFrame = pd.DataFrame(rows)
    return df


def summarize(runs: list[Run]) -> dict[str, Any]:
    if not runs:
        return {"run_count": 0}

    df = to_dataframe(runs)
    successful = df[df["status"] == "converged"]

    return {
        "run_count": len(df),
        "success_rate": float((df["status"] == "converged").mean()),
        "mean_iterations": float(df["iterations"].mean()),
        "mean_convergence_iterations": (
            float(successful["iterations"].mean()) if not successful.empty else None
        ),
        "mean_latency_seconds": float(df["total_latency_seconds"].mean()),
        "total_tokens": int(df["total_tokens"].sum()),
        "mean_tokens_per_run": float(df["total_tokens"].mean()),
        "mean_best_score": float(df["best_score"].mean(skipna=True)),
    }
