"""actuate.engine.execution_engine — the orchestration layer.

Deliberately small (frozen architecture, §4): every line here is
mechanical plumbing — resolve capabilities, call them, build Signals,
append Events, check the algorithm-agnostic safety envelope. No line
branches on *which* Plant/Sensor/Actuator/Controller is bound; that
would be exactly the LoopRunner-conflation this design replaces.

v1 scope: the common topology shape (one `plant`, one or more `sensor`s
feeding one `merge`, one `controller` deciding among one or more
`actuator`s). Router/Decision/Parallel/Tool/HumanApproval node kinds are
defined in the domain model (`domain.nodes.NodeKinds`) but not yet
walked by this engine — a documented, deliberate v1 boundary, not an
oversight.
"""

from __future__ import annotations

import dataclasses
import time
import uuid
from typing import Any

from actuate.domain.events import (
    Event,
    FeedbackPathEntered,
    NodeExecutionCompleted,
    NodeExecutionStarted,
    RunFailed,
    RunStarted,
    RunStatusChanged,
    SignalEmitted,
)
from actuate.domain.capability import CapabilityKinds
from actuate.domain.exceptions import ExecutionError
from actuate.domain.execution_session import ExecutionSession
from actuate.domain.nodes import Node, NodeKinds
from actuate.domain.policy import RetryStrategyName
from actuate.domain.protocols import (
    Controller,
    ConvergencePolicy,
    Corrector,
    EvaluationOutcome,
    Evaluator,
    EventSink,
    Generator,
    MemoryRetriever,
    MeteredGenerator,
    Scheduler,
    SignalFusionStrategy,
)
from actuate.domain.registry import CapabilityRegistry
from actuate.domain.run import Run, RunMode, RunStatus, iterations
from actuate.domain.signals import (
    ControlSignal,
    ObservationSignal,
    OutputSignal,
    PromptSignal,
    TokenUsage,
)
from actuate.domain.specification import Specification
from actuate.engine.controller import RuleBasedController
from actuate.engine.convergence import RuleBasedConvergencePolicy
from actuate.engine.fusion import SingleSignalFusion
from actuate.engine.scheduler import SequentialScheduler
from actuate.retry import RetryingGenerator


def _new_id() -> str:
    return uuid.uuid4().hex


def _nodes_of_kind(specification: Specification, kind: str) -> list[Node]:
    return [n for n in specification.topology.nodes if n.kind == kind]


class ExecutionEngine:
    def __init__(
        self,
        *,
        scheduler: Scheduler | None = None,
        convergence_policy: ConvergencePolicy | None = None,
        event_sinks: list[EventSink] | None = None,
        memory: MemoryRetriever | None = None,
    ) -> None:
        self.scheduler: Scheduler = scheduler or SequentialScheduler()
        self.convergence_policy: ConvergencePolicy = convergence_policy or RuleBasedConvergencePolicy()
        self.event_sinks = event_sinks or []
        self.memory = memory

    async def run(
        self,
        specification: Specification,
        *,
        registry: CapabilityRegistry,
        initial_prompt: str,
        mode: RunMode = "live",
        run_id: str | None = None,
    ) -> Run:
        session = ExecutionSession(
            run_id=run_id or _new_id(), specification_id=specification.id, mode=mode
        )
        await self._append(session, RunStarted(run_id=session.run_id, specification_id=specification.id, mode=mode))
        await self._transition(session, "pending", "running")

        plant_nodes = _nodes_of_kind(specification, NodeKinds.PLANT)
        sensor_nodes = _nodes_of_kind(specification, NodeKinds.SENSOR)
        merge_nodes = _nodes_of_kind(specification, NodeKinds.MERGE)
        actuator_nodes = _nodes_of_kind(specification, NodeKinds.ACTUATOR)
        controller_nodes = _nodes_of_kind(specification, NodeKinds.CONTROLLER)

        if len(plant_nodes) != 1:
            raise ExecutionError(
                f"ExecutionEngine v1 requires exactly one plant node, found {len(plant_nodes)}.",
                node_id="", run_id=session.run_id,
            )
        if not sensor_nodes:
            raise ExecutionError("Topology has no sensor node.", node_id="", run_id=session.run_id)
        if not actuator_nodes:
            raise ExecutionError("Topology has no actuator node.", node_id="", run_id=session.run_id)

        plant_node = plant_nodes[0]
        generator: Generator = self._resolve(registry, plant_node)
        retry_strategy = specification.policies.actuation.retry_strategy
        if retry_strategy != RetryStrategyName.NONE:
            try:
                handler = registry.resolve(CapabilityKinds.RETRY_HANDLER, retry_strategy.value)
                generator = RetryingGenerator(generator, handler)
            except Exception:  # noqa: BLE001 - missing retry capability must not abort the run
                pass
        sensors: list[tuple[Node, Evaluator]] = [
            (node, self._resolve(registry, node)) for node in sensor_nodes
        ]
        judge_plant: Generator = getattr(generator, "inner", generator)
        for _node, evaluator in sensors:
            if hasattr(evaluator, "plant") and getattr(evaluator, "plant") is None:
                evaluator.plant = judge_plant  # type: ignore[attr-defined]
        memory_nodes = _nodes_of_kind(specification, NodeKinds.MEMORY)
        retriever: MemoryRetriever | None = self.memory
        if memory_nodes:
            bound = self._resolve(registry, memory_nodes[0])
            if hasattr(bound, "recall"):
                retriever = bound
        fusion: SignalFusionStrategy = (
            self._resolve(registry, merge_nodes[0]) if merge_nodes else SingleSignalFusion()
        )
        controller: Controller = (
            self._resolve(registry, controller_nodes[0]) if controller_nodes else RuleBasedController()
        )
        actuators: dict[str, tuple[Node, Corrector]] = {}
        for node in actuator_nodes:
            binding = node.capability_binding
            name = binding.name if binding is not None else node.id
            corrector: Corrector = self._resolve(registry, node)
            if retriever is not None and hasattr(corrector, "retriever") and getattr(corrector, "retriever") is None:
                corrector.retriever = retriever  # type: ignore[attr-defined]
            actuators[name] = (node, corrector)

        prompt_text = initial_prompt
        produced_by = "_initial"
        start_time = time.monotonic()
        iteration_index = 0
        context: dict[str, Any] = {}

        while True:
            iteration_index += 1
            await self._append(
                session, FeedbackPathEntered(run_id=session.run_id, iteration_index=iteration_index)
            )

            if retriever is not None:
                recalled = await retriever.recall(prompt_text, top_k=3)
                if recalled:
                    context["retrieved_context"] = "\n".join(record.text for record in recalled)

            prompt_signal = PromptSignal(
                correlation_id=session.run_id,
                produced_by_node=produced_by,
                produced_by_port="prompt",
                text=prompt_text,
            )
            await self._append(session, SignalEmitted(run_id=session.run_id, signal=prompt_signal))

            try:
                output_signal = await self._run_plant(session, plant_node, generator, prompt_signal, context)
            except Exception as exc:  # noqa: BLE001 - recorded as a terminal RunFailed event, not re-raised
                await self._append(
                    session, RunFailed(run_id=session.run_id, node_id=plant_node.id, error=str(exc))
                )
                await self._transition(session, "running", "failed")
                return session.snapshot()

            async def _sensor_task(node: Node, evaluator: Evaluator) -> ObservationSignal:
                return await self._run_sensor(
                    session, node, evaluator, prompt_signal, output_signal, context
                )

            observations = await self.scheduler.dispatch(
                [lambda n=node, e=evaluator: _sensor_task(n, e) for node, evaluator in sensors]
            )

            error_signal = fusion.fuse(observations, set_point=specification.objective)
            error_signal = dataclasses.replace(
                error_signal, correlation_id=session.run_id, parent_signal_id=output_signal.id
            )
            await self._append(session, SignalEmitted(run_id=session.run_id, signal=error_signal))

            elapsed = time.monotonic() - start_time
            history = iterations(session.snapshot())
            status: RunStatus | None = self.convergence_policy.evaluate(
                error=error_signal,
                history=history,
                convergence=specification.policies.convergence,
                stability=specification.policies.stability,
                iteration_index=iteration_index,
                elapsed_seconds=elapsed,
            )
            if status is not None:
                await self._transition(session, "running", status)
                return session.snapshot()

            decision = controller.decide(
                error=error_signal,
                objective=specification.objective,
                actuation=specification.policies.actuation,
                history=history,
                available_actuators=tuple(actuators.keys()),
            )
            actuator_name = decision.actuator_names[0] if decision.actuator_names else next(iter(actuators))
            actuator_node, corrector = actuators[actuator_name]
            evaluation_outcome = (
                _observation_to_outcome(observations[0])
                if observations
                else EvaluationOutcome(score=error_signal.measured)
            )

            control_signal = await self._run_actuator(
                session, actuator_node, corrector, prompt_signal, output_signal,
                evaluation_outcome, decision.effective_gain, context,
            )
            control_signal = dataclasses.replace(
                control_signal, correlation_id=session.run_id, parent_signal_id=error_signal.id
            )
            await self._append(session, SignalEmitted(run_id=session.run_id, signal=control_signal))

            if control_signal.action_kind == "input_mutation" and control_signal.revised_prompt:
                prompt_text = control_signal.revised_prompt
                produced_by = actuator_node.id
            elif control_signal.action_kind == "policy_retune" and control_signal.policy_adjustment:
                context.update(control_signal.policy_adjustment)

    # -- node execution --------------------------------------------------

    async def _run_plant(
        self, session: ExecutionSession, node: Node, generator: Generator,
        prompt: PromptSignal, context: dict[str, Any],
    ) -> OutputSignal:
        await self._append(session, NodeExecutionStarted(run_id=session.run_id, node_id=node.id))
        start = time.monotonic()
        signal: OutputSignal
        if isinstance(generator, MeteredGenerator):
            outcome = await generator.generate_with_metadata(prompt.text, context=context)
            signal = OutputSignal(
                correlation_id=session.run_id, produced_by_node=node.id, produced_by_port="output",
                parent_signal_id=prompt.id, text=outcome.text, latency_seconds=outcome.latency_seconds,
                usage=TokenUsage(
                    prompt_tokens=outcome.prompt_tokens, completion_tokens=outcome.completion_tokens,
                    total_tokens=outcome.prompt_tokens + outcome.completion_tokens,
                ),
            )
        else:
            text = await generator.generate(prompt.text, context=context)
            signal = OutputSignal(
                correlation_id=session.run_id, produced_by_node=node.id, produced_by_port="output",
                parent_signal_id=prompt.id, text=text, latency_seconds=time.monotonic() - start,
            )
        await self._append(session, SignalEmitted(run_id=session.run_id, signal=signal))
        await self._append(
            session,
            NodeExecutionCompleted(
                run_id=session.run_id, node_id=node.id, produced_signal_ids=(signal.id,),
                duration_seconds=time.monotonic() - start,
            ),
        )
        return signal

    async def _run_sensor(
        self, session: ExecutionSession, node: Node, evaluator: Evaluator,
        prompt: PromptSignal, output: OutputSignal, context: dict[str, Any],
    ) -> ObservationSignal:
        await self._append(session, NodeExecutionStarted(run_id=session.run_id, node_id=node.id))
        start = time.monotonic()
        outcome = await evaluator.evaluate(prompt=prompt.text, output=output.text, context=context)
        binding = node.capability_binding
        sensor_id = binding.name if binding is not None else node.id
        signal = ObservationSignal(
            correlation_id=session.run_id, produced_by_node=node.id, produced_by_port="observation",
            parent_signal_id=output.id, sensor_id=sensor_id, score=outcome.score,
            passed=outcome.passed, feedback=outcome.feedback, details=outcome.details,
        )
        await self._append(session, SignalEmitted(run_id=session.run_id, signal=signal))
        await self._append(
            session,
            NodeExecutionCompleted(
                run_id=session.run_id, node_id=node.id, produced_signal_ids=(signal.id,),
                duration_seconds=time.monotonic() - start,
            ),
        )
        return signal

    async def _run_actuator(
        self, session: ExecutionSession, node: Node, corrector: Corrector,
        prompt: PromptSignal, output: OutputSignal, evaluation: EvaluationOutcome,
        gain: float, context: dict[str, Any],
    ) -> ControlSignal:
        await self._append(session, NodeExecutionStarted(run_id=session.run_id, node_id=node.id))
        start = time.monotonic()
        outcome = await corrector.correct(
            prompt=prompt.text, output=output.text, evaluation=evaluation, gain=gain, context=context
        )
        binding = node.capability_binding
        actuator_id = binding.name if binding is not None else node.id
        action_kind: Any = outcome.action_kind
        signal = ControlSignal(
            correlation_id=session.run_id, produced_by_node=node.id, produced_by_port="prompt_mutation",
            actuator_id=actuator_id, action_kind=action_kind,
            revised_prompt=outcome.revised_prompt, policy_adjustment=outcome.policy_adjustment,
            notes=outcome.notes,
        )
        await self._append(
            session,
            NodeExecutionCompleted(
                run_id=session.run_id, node_id=node.id, produced_signal_ids=(signal.id,),
                duration_seconds=time.monotonic() - start,
            ),
        )
        return signal

    # -- helpers -----------------------------------------------------------

    def _resolve(self, registry: CapabilityRegistry, node: Node) -> Any:
        binding = node.capability_binding
        if binding is None:
            raise ExecutionError(
                f"Node '{node.id}' has no capability_binding.", node_id=node.id, run_id=""
            )
        return registry.resolve(binding.kind, binding.name, **binding.params)

    async def _append(self, session: ExecutionSession, event: Event) -> None:
        session.emit(event)
        for sink in self.event_sinks:
            await sink.handle(event)

    async def _transition(self, session: ExecutionSession, from_status: str, to_status: RunStatus) -> None:
        await self._append(
            session,
            RunStatusChanged(run_id=session.run_id, from_status=from_status, to_status=to_status),
        )


def _observation_to_outcome(observation: ObservationSignal) -> EvaluationOutcome:
    return EvaluationOutcome(
        score=observation.score, passed=observation.passed,
        feedback=observation.feedback, details=observation.details,
    )
