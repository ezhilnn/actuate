"""PID-style controller — still topology-blind, only sees error/history."""

from __future__ import annotations

from actuate.domain.policy import ActuationPolicy, SetPoint
from actuate.domain.protocols import ControlDecision
from actuate.domain.run import IterationView
from actuate.domain.signals import ErrorSignal


class PIDController:
    def __init__(self, *, kp: float = 0.8, ki: float = 0.05, kd: float = 0.1) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral = 0.0
        self._last_error = 0.0

    def decide(
        self,
        *,
        error: ErrorSignal,
        objective: SetPoint,
        actuation: ActuationPolicy,
        history: list[IterationView],
        available_actuators: tuple[str, ...],
    ) -> ControlDecision:
        if not available_actuators:
            raise ValueError("PIDController requires at least one available actuator.")
        e = error.error
        self._integral += e
        derivative = e - self._last_error
        self._last_error = e
        raw = self.kp * e + self.ki * self._integral + self.kd * derivative
        gain = max(0.05, min(1.0, abs(raw)))
        name = available_actuators[0]
        if len(available_actuators) > 1 and gain > 0.7:
            name = available_actuators[-1]
        return ControlDecision(
            actuator_names=(name,),
            effective_gain=gain,
            converged_hint=error.within_tolerance,
            notes=f"pid kp={self.kp} gain={gain:.3f} (setpoint={objective.target}, base={actuation.gain})",
        )
