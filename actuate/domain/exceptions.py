"""actuate.domain.exceptions — the base error hierarchy for the whole
framework. Every exception raised anywhere in `actuate` inherits from
`ActuateError`.
"""

from __future__ import annotations


class ActuateError(Exception):
    """Base class for every exception raised by Actuate."""


class TopologyValidationError(ActuateError):
    """Raised when a `Topology` fails validation (port-type mismatch,
    unreachable feedback path under the active `TopologyValidationPolicy`,
    duplicate node ids, etc.) — always raised at `Specification` creation
    time, never at Run time.
    """


class PortMismatchError(TopologyValidationError):
    """An `Edge` connects an output port to an input port whose
    `signal_kind` is incompatible.
    """


class CapabilityResolutionError(ActuateError):
    """Raised when a `CapabilityRegistry` cannot resolve a requested
    `(kind, name)` pair, or when a registered factory's output doesn't
    satisfy the Protocol declared for that capability kind.
    """


class ExecutionError(ActuateError):
    """Raised when a bound capability fails during execution in a way
    the engine does not itself recover from (a `Plant`/`Sensor`/
    `Actuator`/`Controller` call that raised and was not retried away).
    """

    def __init__(self, message: str, *, node_id: str, run_id: str) -> None:
        super().__init__(f"[node={node_id} run={run_id}] {message}")
        self.node_id = node_id
        self.run_id = run_id


class PolicyViolationError(ActuateError):
    """Raised when a `LoopPolicy` (or one of its parts) is configured
    with internally contradictory values.
    """
