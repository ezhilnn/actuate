"""actuate.engine.fusion — SignalFusionStrategy implementations, bound to
`merge` nodes. Subsumes what LoopForge v1 called `SignalAggregator`.

Each strategy builds an ErrorSignal with `correlation_id=""` as a
placeholder — capabilities are deliberately engine/session-blind (same
two-layer separation as every other Protocol in `domain.protocols`), so
they can't know the Run's correlation id. `ExecutionEngine` fixes this up
via `dataclasses.replace()` immediately before emitting the signal.
"""

from __future__ import annotations

from actuate.domain.policy import SetPoint
from actuate.domain.signals import ErrorSignal, ObservationSignal


class SingleSignalFusion:
    """Default: exactly one ObservationSignal, passed through unchanged.
    Reproduces LoopForge v1's implicit single-evaluator behavior with
    zero configuration for the common case.
    """

    def fuse(
        self, observations: list[ObservationSignal], *, set_point: SetPoint
    ) -> ErrorSignal:
        if not observations:
            raise ValueError("SingleSignalFusion requires at least one ObservationSignal.")
        return _build_error_signal(observations[0].score, set_point)


class WeightedMeanFusion:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {}

    def fuse(
        self, observations: list[ObservationSignal], *, set_point: SetPoint
    ) -> ErrorSignal:
        if not observations:
            raise ValueError("WeightedMeanFusion requires at least one ObservationSignal.")
        total_weight = sum(self.weights.get(o.sensor_id, 1.0) for o in observations)
        weighted = sum(o.score * self.weights.get(o.sensor_id, 1.0) for o in observations)
        measured = weighted / total_weight if total_weight else 0.0
        return _build_error_signal(measured, set_point)


class WorstCaseFusion:
    """Every sensor must be satisfied — the aggregate score is the
    minimum across all observations.
    """

    def fuse(
        self, observations: list[ObservationSignal], *, set_point: SetPoint
    ) -> ErrorSignal:
        if not observations:
            raise ValueError("WorstCaseFusion requires at least one ObservationSignal.")
        measured = min(o.score for o in observations)
        return _build_error_signal(measured, set_point)


def _build_error_signal(measured: float, set_point: SetPoint) -> ErrorSignal:
    return ErrorSignal(
        correlation_id="",
        produced_by_node="merge",
        produced_by_port="error",
        setpoint=set_point.target,
        measured=measured,
        error=set_point.target - measured,
        within_tolerance=measured >= set_point.target,
    )
