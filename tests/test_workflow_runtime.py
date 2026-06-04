import unittest

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.task import StepResult, StepStatus, Task, TaskStatus, WorkflowSpec, WorkflowStep
from app.workflows.checkpoints import CheckpointManager
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.runtime import WorkflowRuntimePlan
from app.workflows.spec_to_agent import build_spec_to_agent_definition


class WorkflowRuntimePlanTests(unittest.TestCase):
    def test_rejects_duplicate_step_ids(self):
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[
                WorkflowStep(id="same", type="context", title="A"),
                WorkflowStep(id="same", type="agent", title="B"),
            ],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual(raised.exception.code, "workflow.duplicate_step_id")

    def test_rejects_dangling_routes(self):
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[WorkflowStep(id="a", type="context", title="A", on_success="missing")],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual(raised.exception.code, "workflow.dangling_route")

    def test_groups_contiguous_parallel_steps(self):
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="context", title="A"),
                WorkflowStep(id="b", type="agent", title="B", parallel_group="reviewers"),
                WorkflowStep(id="c", type="agent", title="C", parallel_group="reviewers"),
                WorkflowStep(id="d", type="gate", title="D"),
            ],
        )

        plan = WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual(
            [[step.id for step in batch.steps] for batch in plan.batches_from("a")],
            [["a"], ["b", "c"], ["d"]],
        )

    def test_result_next_step_overrides_step_success_route(self):
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="gate", title="A", on_success="b"),
                WorkflowStep(id="b", type="agent", title="B"),
                WorkflowStep(id="c", type="agent", title="C"),
            ],
        )
        plan = WorkflowRuntimePlan.from_workflow(workflow)
        result = StepResult("a", StepStatus.SUCCEEDED, next_step_id="c")

        self.assertEqual(plan.resolve_success_route("a", result), "c")


class WorkflowCheckpointManagerTests(unittest.TestCase):
    def test_resume_uses_checkpoint_next_step_when_not_waiting_for_user(self):
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": "running"}

        self.assertEqual(manager.resume_step_id(checkpoint), "writer")

    def test_resume_ignores_waiting_user_checkpoint(self):
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": TaskStatus.WAITING_FOR_USER.value}

        self.assertIsNone(manager.resume_step_id(checkpoint))

    def test_build_transaction_checkpoint_payload(self):
        manager = CheckpointManager(storage=None)
        payload = manager.build_payload(
            task_id="task_1",
            run_id="run_1",
            last_completed_step_id="a",
            next_step_id="b",
            status="running",
            attempt=2,
            completed_step_ids=["a"],
        )

        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["completed_step_ids"], ["a"])


class ContextCompilerServiceTests(unittest.TestCase):
    def make_native_task(self):
        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_1",
            task_type="spec_to_agent",
            username="alice",
            goal="Compile login requirements",
            title="Login",
            inputs={"business_intent": "Users must log in safely"},
        )
        return Task(definition=definition, context=context, task_id="task_1")

    def test_renders_native_machine_spec_payload(self):
        task = self.make_native_task()
        step = next(step for step in task.definition.workflow.steps if step.id == "writer_machine_spec")
        compiler = ContextCompilerService()

        name, content = compiler.artifact_payload(task, step)

        self.assertEqual(name, "machine_spec.yaml")
        self.assertIn("source of truth", content.lower())
        self.assertIn("Users must log in safely", content)

    def test_rejects_native_artifact_without_single_output_key(self):
        task = self.make_native_task()
        bad_step = WorkflowStep(id="bad", type="artifact", title="Bad", output_keys=[])
        compiler = ContextCompilerService()

        with self.assertRaises(DomainError) as raised:
            compiler.artifact_payload(task, bad_step)

        self.assertEqual(raised.exception.code, "workflow.native_artifact_contract_invalid")


if __name__ == "__main__":
    unittest.main()

from app.core.task import TaskDefinition
from app.core.tools import ToolPolicy
from app.workflows.executors import StepExecutionRegistry, StepExecutor
from app.workflows.dag_runtime import PlaybookDAGRuntime
from app.workflows.checkpoints import CheckpointReplay


class PlaybookDAGRuntimeTests(unittest.TestCase):
    def test_frontier_returns_all_dependency_ready_nodes(self):
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="context", title="A"),
                WorkflowStep(id="b", type="agent", title="B", input_keys=["a"]),
                WorkflowStep(id="c", type="agent", title="C", input_keys=["a"]),
                WorkflowStep(id="d", type="gate", title="D", input_keys=["b", "c"]),
            ],
        )
        runtime = PlaybookDAGRuntime.from_workflow(workflow)

        self.assertEqual(runtime.ready_node_ids(completed=set()), ["a"])
        self.assertEqual(runtime.ready_node_ids(completed={"a"}), ["b", "c"])
        self.assertEqual(runtime.ready_node_ids(completed={"a", "b"}), ["c"])
        self.assertEqual(runtime.ready_node_ids(completed={"a", "b", "c"}), ["d"])

    def test_conditions_route_by_context_value(self):
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="gate", type="gate", title="Gate", on_success="fast", on_failure="slow"),
                WorkflowStep(id="fast", type="agent", title="Fast"),
                WorkflowStep(id="slow", type="agent", title="Slow"),
            ],
        )
        runtime = PlaybookDAGRuntime.from_workflow(workflow)

        self.assertEqual(runtime.route_for("gate", {"status": "succeeded"}), "fast")
        self.assertEqual(runtime.route_for("gate", {"status": "failed"}), "slow")

    def test_rejects_dependency_cycle(self):
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="agent", title="A", input_keys=["b"]),
                WorkflowStep(id="b", type="agent", title="B", input_keys=["a"]),
            ],
        )

        with self.assertRaises(DomainError) as raised:
            PlaybookDAGRuntime.from_workflow(workflow)

        self.assertEqual(raised.exception.code, "workflow.dag_cycle")


class CheckpointReplayTests(unittest.TestCase):
    def test_replay_reconstructs_completed_steps_and_last_checkpoint(self):
        events = [
            {"type": "workflow.step.completed", "payload": {"step_id": "a", "run_id": "run_1"}},
            {"type": "workflow.step.completed", "payload": {"step_id": "b", "run_id": "run_1"}},
            {"type": "workflow.step.failed", "payload": {"step_id": "c", "run_id": "run_1"}},
        ]

        replay = CheckpointReplay.from_events("task_1", events)

        self.assertEqual(replay.completed_step_ids, ["a", "b"])
        self.assertEqual(replay.failed_step_id, "c")
        self.assertEqual(replay.next_attempt_for("c"), 2)

    def test_replay_counts_multiple_attempts(self):
        events = [
            {"type": "workflow.step.started", "payload": {"step_id": "a"}},
            {"type": "workflow.step.failed", "payload": {"step_id": "a"}},
            {"type": "workflow.step.started", "payload": {"step_id": "a"}},
            {"type": "workflow.step.completed", "payload": {"step_id": "a"}},
        ]

        replay = CheckpointReplay.from_events("task_1", events)

        self.assertEqual(replay.attempts_by_step["a"], 2)
        self.assertEqual(replay.next_attempt_for("a"), 3)


class StepExecutionRegistryTests(unittest.TestCase):
    def test_dispatches_executor_by_step_type(self):
        class DummyExecutor(StepExecutor):
            step_type = "dummy"

            def run(self, task, step, *, run_id=None, is_parallel=False):
                return StepResult(step.id, StepStatus.SUCCEEDED, outputs={"ok": True})

        registry = StepExecutionRegistry([DummyExecutor()])
        step = WorkflowStep(id="x", type="dummy", title="X")

        result = registry.run(None, step, run_id="run_1")

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.outputs, {"ok": True})

    def test_unknown_executor_returns_failed_result(self):
        registry = StepExecutionRegistry([])
        step = WorkflowStep(id="x", type="unknown", title="X")

        result = registry.run(None, step)

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.error.code, "workflow.unknown_step_type")


from app.workflows.executors import (
    ArtifactStepExecutor,
    CheckpointStepExecutor,
    ContextStepExecutor,
    DefaultStepExecutorRegistryFactory,
    DiffStepExecutor,
)


class BuiltInStepExecutorsTests(unittest.TestCase):
    def make_task(self):
        definition = TaskDefinition(
            type="executor_test",
            display_name="Executor Test",
            input_schema={},
            workflow=WorkflowSpec(name="executor", version="1.0", steps=[]),
            tool_policy=ToolPolicy(task_type="executor_test"),
        )
        context = TaskContext(
            task_id="task_exec",
            task_type="executor_test",
            username="alice",
            goal="Run executors",
            title="Executors",
        )
        return Task(definition=definition, context=context, task_id="task_exec")

    def test_context_executor_marks_context_ready(self):
        task = self.make_task()
        executor = ContextStepExecutor()
        step = WorkflowStep(id="load", type="context", title="Load")

        result = executor.run(task, step)

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.outputs["goal"], "Run executors")

    def test_diff_and_checkpoint_executors_return_structured_outputs(self):
        task = self.make_task()
        diff = DiffStepExecutor().run(task, WorkflowStep(id="diff", type="diff", title="Diff"))
        checkpoint = CheckpointStepExecutor().run(task, WorkflowStep(id="cp", type="checkpoint", title="Checkpoint"))

        self.assertEqual(diff.outputs, {"candidates": []})
        self.assertEqual(checkpoint.outputs, {"checkpoint": "cp"})

    def test_artifact_executor_uses_context_compiler_and_tool_service(self):
        class RecordingToolService:
            def __init__(self):
                self.calls = []

            def invoke(self, definition, context, call):
                from app.core.artifacts import Artifact
                from app.core.tools import ToolResult
                self.calls.append(call)
                return ToolResult(
                    call_id=call.id,
                    status="succeeded",
                    artifacts=[Artifact(artifact_id="artifact_1", task_id=context.task_id, name=call.arguments["name"], version=1)],
                )

        task = self.make_task()
        task.context.step_outputs["writer_scene_docs"] = {"artifact_name": "模块概览.md", "artifact_content": "content"}
        tool_service = RecordingToolService()
        executor = ArtifactStepExecutor(tool_service=tool_service, context_compiler=ContextCompilerService())

        result = executor.run(task, WorkflowStep(id="writer", type="artifact", title="Write", role="Writer"))

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(tool_service.calls[0].tool_name, "artifact.write")
        self.assertEqual(task.context.artifacts[0].name, "模块概览.md")

    def test_default_factory_registers_core_executor_types(self):
        registry = DefaultStepExecutorRegistryFactory(
            tool_service=None,
            llm=None,
            storage=None,
            context_compiler=ContextCompilerService(),
        ).build()

        for step_type in ["context", "agent", "gate", "arbitration", "artifact", "diff", "checkpoint"]:
            self.assertIsNotNone(registry.get(step_type))

from app.workflows.retry_policy import RetryDecision, RetryPolicyRuntime
from app.workflows.state_store import WorkflowStateStore, WorkflowRollbackPlanner


class RetryPolicyRuntimeTests(unittest.TestCase):
    def test_allows_retry_until_max_attempts(self):
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="fragile",
            type="agent",
            title="Fragile",
            retry_policy={"max_attempts": 3, "backoff_seconds": 2},
        )

        first = runtime.evaluate(step, attempt=1, elapsed_ms=25, error_code="TemporaryError")
        third = runtime.evaluate(step, attempt=3, elapsed_ms=25, error_code="TemporaryError")

        self.assertEqual(first.decision, RetryDecision.RETRY)
        self.assertEqual(first.next_attempt, 2)
        self.assertEqual(first.delay_seconds, 2)
        self.assertEqual(third.decision, RetryDecision.GIVE_UP)
        self.assertEqual(third.reason, "max_attempts_exhausted")

    def test_timeout_breaks_before_retry(self):
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="slow",
            type="agent",
            title="Slow",
            retry_policy={"max_attempts": 3, "timeout_ms": 10},
        )

        decision = runtime.evaluate(step, attempt=1, elapsed_ms=50, error_code="Timeout")

        self.assertEqual(decision.decision, RetryDecision.TIMEOUT)
        self.assertEqual(decision.reason, "timeout_exceeded")

    def test_non_retryable_error_trips_circuit(self):
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="denied",
            type="artifact",
            title="Denied",
            retry_policy={"max_attempts": 3, "non_retryable_errors": ["tool.denied"]},
        )

        decision = runtime.evaluate(step, attempt=1, elapsed_ms=1, error_code="tool.denied")

        self.assertEqual(decision.decision, RetryDecision.CIRCUIT_OPEN)
        self.assertEqual(decision.reason, "non_retryable_error")

    def test_event_payload_hides_error_message_but_keeps_error_code(self):
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(id="fragile", type="agent", title="Fragile", retry_policy={"max_attempts": 2})
        decision = runtime.evaluate(step, attempt=1, elapsed_ms=5, error_code="TemporaryError")

        payload = runtime.to_event_payload(step, decision, error_message="secret prompt contents")

        self.assertEqual(payload["step_id"], "fragile")
        self.assertEqual(payload["error_code"], "TemporaryError")
        self.assertNotIn("secret", str(payload))


class WorkflowStateStoreTests(unittest.TestCase):
    def test_records_run_and_checkpoint_history(self):
        store = WorkflowStateStore()

        store.record_run_started("task_1", "run_1", start_step_id="a")
        store.record_checkpoint(
            "task_1",
            {"run_id": "run_1", "last_completed_step_id": "a", "next_step_id": "b", "status": "running"},
        )
        store.record_run_finished("task_1", "run_1", status="completed")

        history = store.run_history("task_1")
        checkpoints = store.checkpoint_history("task_1")

        self.assertEqual(history[0]["event"], "run.started")
        self.assertEqual(history[-1]["event"], "run.finished")
        self.assertEqual(checkpoints[0]["last_completed_step_id"], "a")

    def test_rollback_plan_selects_previous_complete_checkpoint(self):
        store = WorkflowStateStore()
        store.record_checkpoint("task_1", {"last_completed_step_id": "a", "next_step_id": "b", "status": "running"})
        store.record_checkpoint("task_1", {"last_completed_step_id": "b", "next_step_id": "c", "status": "running"})
        planner = WorkflowRollbackPlanner(store)

        plan = planner.plan_rollback("task_1", failed_step_id="c")

        self.assertEqual(plan.rollback_to_step_id, "b")
        self.assertEqual(plan.resume_step_id, "c")
        self.assertEqual(plan.discarded_step_ids, ["c"])

    def test_store_can_restore_from_storage_events(self):
        class EventObj:
            def __init__(self, type, payload):
                self.type = type
                self.payload = payload

        events = [
            EventObj("workflow.run.started", {"run_id": "run_1", "start_step_id": "a"}),
            EventObj("workflow.step.completed", {"step_id": "a", "run_id": "run_1"}),
            EventObj("workflow.run.completed", {"run_id": "run_1", "task_status": "completed"}),
        ]

        store = WorkflowStateStore.from_events("task_1", events)

        self.assertEqual(store.run_history("task_1")[0]["run_id"], "run_1")
        self.assertEqual(store.checkpoint_history("task_1")[0]["last_completed_step_id"], "a")


class WorkflowEngineRetryIntegrationTests(unittest.TestCase):
    def test_agent_step_retries_once_then_succeeds(self):
        import tempfile
        from pathlib import Path

        from app.services.fakes import FakeKnowledge, FakeStorage
        from app.services.task_service import TaskService
        from app.services.tool_service import ToolService
        from app.workflows.engine import WorkflowEngine

        class FlakyLLM:
            def __init__(self):
                self.calls = 0

            def invoke_stream(self, role, prompt, context, telemetry=None):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary provider outage")
                yield "ok"

            def invoke(self, role, prompt, context):
                from app.core.ports import LLMResult
                return LLMResult(content="PASS", structured={"role": role})

        workflow = WorkflowSpec(
            name="retry_agent",
            version="1.0",
            steps=[
                WorkflowStep(id="draft", type="agent", title="Draft", role="PM", retry_policy={"max_attempts": 2}),
                WorkflowStep(id="final", type="checkpoint", title="Final"),
            ],
        )
        definition = TaskDefinition(
            type="retry_agent",
            display_name="Retry Agent",
            input_schema={"required": ["username"], "properties": {"username": {"type": "string"}}},
            workflow=workflow,
            tool_policy=ToolPolicy(task_type="retry_agent"),
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        storage = FakeStorage(Path(temp.name))
        engine = WorkflowEngine(
            tool_service=ToolService.default(root=Path(temp.name), knowledge=FakeKnowledge()),
            llm=FlakyLLM(),
            storage=storage,
        )
        service = TaskService(registry={"retry_agent": definition}, engine=engine, storage=storage)
        task = service.create_task("retry_agent", {"username": "alice", "goal": "retry"})

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        event_types = [event.type for event in storage.read_events(task.task_id)]
        self.assertIn("workflow.step.retry_scheduled", event_types)
        self.assertIn("workflow.step.completed", event_types)

    def test_agent_step_emits_retry_exhausted_when_attempts_run_out(self):
        import tempfile
        from pathlib import Path

        from app.services.fakes import FakeKnowledge, FakeStorage
        from app.services.task_service import TaskService
        from app.services.tool_service import ToolService
        from app.workflows.engine import WorkflowEngine

        class FailingLLM:
            def invoke_stream(self, role, prompt, context, telemetry=None):
                raise RuntimeError("provider down with private prompt")

            def invoke(self, role, prompt, context):
                from app.core.ports import LLMResult
                return LLMResult(content="FAIL", structured={"role": role})

        workflow = WorkflowSpec(
            name="retry_agent",
            version="1.0",
            steps=[WorkflowStep(id="draft", type="agent", title="Draft", role="PM", retry_policy={"max_attempts": 2})],
        )
        definition = TaskDefinition(
            type="retry_agent",
            display_name="Retry Agent",
            input_schema={"required": ["username"], "properties": {"username": {"type": "string"}}},
            workflow=workflow,
            tool_policy=ToolPolicy(task_type="retry_agent"),
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        storage = FakeStorage(Path(temp.name))
        engine = WorkflowEngine(
            tool_service=ToolService.default(root=Path(temp.name), knowledge=FakeKnowledge()),
            llm=FailingLLM(),
            storage=storage,
        )
        service = TaskService(registry={"retry_agent": definition}, engine=engine, storage=storage)
        task = service.create_task("retry_agent", {"username": "alice", "goal": "retry"})

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.FAILED)
        retry_events = [event.to_dict() for event in storage.read_events(task.task_id) if event.type == "workflow.step.retry_exhausted"]
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(retry_events[0]["payload"]["error_code"], "RuntimeError")
        self.assertNotIn("private prompt", str(retry_events[0]["payload"]))
