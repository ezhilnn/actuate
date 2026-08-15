"""actuate.engine.convergence — RuleBasedConvergencePolicy.

Combines what LoopForge v1 split across `LoopPolicy.check_convergence`
and a separate `OscillationDetector` into one pluggable `ConvergencePolicy`
capability, operating on `IterationView` history (a projection over the
Run's EventLog) instead of raw parallel lists.
"""

from __future__ import annotations

import itertools
import statistics

from actuate.domain.policy import ConvergenceCriteria, StabilityGuard
from actuate.domain.run import IterationView, RunStatus
from actuate.domain.signals import ErrorSignal


class RuleBasedConvergencePolicy:
    def __init__(
        self,
        *,
        oscillation_window: int = 4,
        oscillation_variance_threshold: float = 0.02,
    ) -> None:
        self.oscillation_window = oscillation_window
        self.oscillation_variance_threshold = oscillation_variance_threshold

    def evaluate(
        self,
        *,
        error: ErrorSignal,
        history: list[IterationView],
        convergence: ConvergenceCriteria,
        stability: StabilityGuard,
        iteration_index: int,
        elapsed_seconds: float,
    ) -> RunStatus | None:
        if stability.timeout_seconds is not None and elapsed_seconds > stability.timeout_seconds:
            return "timed_out"

        if error.within_tolerance:
            return "converged"

        scores = [v.error_signal.measured for v in history if v.error_signal is not None]
        if not scores or scores[-1] != error.measured:
            scores = [*scores, error.measured]

        outputs = [v.output.text for v in history if v.output is not None]

        if self._is_oscillating(outputs, scores):
            return "oscillating"

        if len(scores) > convergence.patience:
            recent = scores[-(convergence.patience + 1) :]
            deltas = [b - a for a, b in itertools.pairwise(recent)]
            if all(delta < convergence.min_improvement for delta in deltas):
                return "exhausted"

        if iteration_index >= stability.max_iterations:
            return "exhausted"

        return None

    def _is_oscillating(self, outputs: list[str], scores: list[float]) -> bool:
        if self._repeated_pattern(outputs):
            return True
        return self._high_variance_no_trend(scores)

    def _repeated_pattern(self, outputs: list[str]) -> bool:
        if len(outputs) < 4:
            return False
        tail = outputs[-self.oscillation_window :]
        for cycle_len in (2, 3):
            if len(tail) < cycle_len * 2:
                continue
            if tail[-cycle_len:] == tail[-cycle_len * 2 : -cycle_len]:
                return True
        return False

    def _high_variance_no_trend(self, scores: list[float]) -> bool:
        if len(scores) < self.oscillation_window:
            return False
        recent = scores[-self.oscillation_window :]
        variance = statistics.pvariance(recent)
        trending_up = recent[-1] > recent[0]
        return variance > self.oscillation_variance_threshold and not trending_up
