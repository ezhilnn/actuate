"""actuate.domain — Phase A: pure domain model, zero I/O.

Everything else in the framework (engine, plants, sensors, actuators,
retry, memory, telemetry, persistence, dsl, capabilities, ui) depends on
this package. This package depends on nothing else in `actuate`.
"""

from actuate.domain.capability import (
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityKinds,
    CapabilityRef,
)
from actuate.domain.control_system import ControlSystem, Workspace
from actuate.domain.events import (
    Event,
    EventLog,
    FeedbackPathEntered,
    NodeExecutionCompleted,
    NodeExecutionStarted,
    RunFailed,
    RunStarted,
    RunStatusChanged,
    SignalEmitted,
)
from actuate.domain.exceptions import (
    ActuateError,
    CapabilityResolutionError,
    ExecutionError,
    PolicyViolationError,
    PortMismatchError,
    TopologyValidationError,
)
from actuate.domain.execution_session import ExecutionSession
from actuate.domain.nodes import Node, NodeKind, NodeKinds
from actuate.domain.policy import (
    ActuationPolicy,
    ConvergenceCriteria,
    LoopPolicy,
    RetryStrategyName,
    SetPoint,
    StabilityGuard,
)
from actuate.domain.ports import Edge, Port
from actuate.domain.protocols import (
    ArtifactStore,
    ControlDecision,
    Controller,
    ConvergencePolicy,
    CorrectionOutcome,
    Corrector,
    EvaluationOutcome,
    Evaluator,
    EventSink,
    GenerationOutcome,
    Generator,
    MemoryRetriever,
    MemoryStore,
    MeteredGenerator,
    RetryAttempt,
    RetryHandler,
    RoutingStrategy,
    RunStore,
    Scheduler,
    SignalFusionStrategy,
)
from actuate.domain.registry import CapabilityRegistry
from actuate.domain.run import (
    IterationView,
    Run,
    RunMetricsView,
    RunMode,
    RunStatus,
    all_events,
    convergence_progress,
    current_status,
    ended_at,
    failure_reason,
    iterations,
    metrics,
    started_at,
)
from actuate.domain.signals import (
    ArtifactRef,
    ContextSignal,
    ControlSignal,
    ErrorSignal,
    MemoryRecord,
    MemorySignal,
    ObservationSignal,
    OutputSignal,
    PromptSignal,
    Signal,
    TokenUsage,
)
from actuate.domain.templates import standard_closed_loop
from actuate.domain.topology import (
    AllowAnyTopology,
    RequireFeedbackPath,
    Topology,
    TopologyValidationPolicy,
)

__all__ = [  # noqa: RUF022 - deliberately grouped by category, not alphabetical
    # capability
    "CapabilityDescriptor",
    "CapabilityKind",
    "CapabilityKinds",
    "CapabilityRef",
    "CapabilityRegistry",
    # control system / workspace
    "ControlSystem",
    "Workspace",
    # events
    "Event",
    "EventLog",
    "FeedbackPathEntered",
    "NodeExecutionCompleted",
    "NodeExecutionStarted",
    "RunFailed",
    "RunStarted",
    "RunStatusChanged",
    "SignalEmitted",
    # exceptions
    "ActuateError",
    "CapabilityResolutionError",
    "ExecutionError",
    "PolicyViolationError",
    "PortMismatchError",
    "TopologyValidationError",
    # execution session
    "ExecutionSession",
    # nodes / ports / topology
    "Node",
    "NodeKind",
    "NodeKinds",
    "Edge",
    "Port",
    "Topology",
    "TopologyValidationPolicy",
    "RequireFeedbackPath",
    "AllowAnyTopology",
    # policy
    "ActuationPolicy",
    "ConvergenceCriteria",
    "LoopPolicy",
    "RetryStrategyName",
    "SetPoint",
    "StabilityGuard",
    # protocols
    "ArtifactStore",
    "ControlDecision",
    "Controller",
    "Corrector",
    "CorrectionOutcome",
    "ConvergencePolicy",
    "EventSink",
    "Evaluator",
    "EvaluationOutcome",
    "Generator",
    "GenerationOutcome",
    "MemoryRetriever",
    "MemoryStore",
    "MeteredGenerator",
    "RetryAttempt",
    "RetryHandler",
    "RoutingStrategy",
    "RunStore",
    "Scheduler",
    "SignalFusionStrategy",
    # run / projections
    "IterationView",
    "Run",
    "RunMetricsView",
    "RunMode",
    "RunStatus",
    "all_events",
    "convergence_progress",
    "current_status",
    "ended_at",
    "failure_reason",
    "iterations",
    "metrics",
    "started_at",
    # signals
    "ArtifactRef",
    "ContextSignal",
    "ControlSignal",
    "ErrorSignal",
    "MemoryRecord",
    "MemorySignal",
    "ObservationSignal",
    "OutputSignal",
    "PromptSignal",
    "Signal",
    "TokenUsage",
    # specification
    "Specification",
    "create_specification",
]
