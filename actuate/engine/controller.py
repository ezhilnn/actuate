"""actuate.engine.controller — RuleBasedController, the default (and, for
v1, only shipped) Controller capability.

Deliberately topology-blind: this class imports nothing from
`domain.nodes`/`domain.ports`/`domain.topology`, and its `decide()`
signature (inherited from `domain.protocols.Controller`) has no
parameter through which a Node/Port/Topology could arrive — see the
frozen architecture, §5 of the second review.

A `PIDController` or other pluggable control algorithm is a drop-in
replacement satisfying the same Protocol — not sketched here, left for
whoever wants to demonstrate it, since the Protocol itself is what
proves pluggability, not any one additional implementation.
"""

from __future__ import annotations

from actuate.domain.policy import ActuationPolicy, SetPoint
from actuate.domain.protocols import ControlDecision
from actuate.domain.run import IterationView
from actuate.domain.signals import ErrorSignal


class RuleBasedController:
    """Reproduces LoopForge v1's implicit behavior: always escalate to
    whichever actuator(s) are available, at the statically configured
    gain. This is the "FirstAvailableSelector" default from the frozen
    architecture's node-taxonomy discussion, expressed as a Controller.
    """

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
            raise ValueError("RuleBasedController requires at least one available actuator.")
        return ControlDecision(
            actuator_names=(available_actuators[0],),
            effective_gain=actuation.gain,
            converged_hint=error.within_tolerance,
            notes=f"rule-based: escalate to '{available_actuators[0]}' at gain={actuation.gain}",
        )
