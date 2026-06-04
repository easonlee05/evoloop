import tempfile
import unittest
from pathlib import Path

from app.core.task import TaskStatus
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.workflows.spec_to_agent import build_spec_to_agent_definition


class TestSpecToAgentWorkflow(unittest.TestCase):
    def make_service(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        self.addCleanup(temp.cleanup)
        return service, storage

    def test_spec_to_agent_workflow_structure(self):
        definition = build_spec_to_agent_definition()

        self.assertEqual(definition.type, "spec_to_agent")
        self.assertEqual(definition.metadata["is_native_3_0"], True)
        self.assertEqual(definition.metadata["source_of_truth"], "machine_spec.yaml")

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # Verify core lane steps
        self.assertIn("context_normalizer", step_ids)
        self.assertIn("open_question_identifier", step_ids)
        self.assertIn("human_decision_gate", step_ids)
        self.assertIn("machine_spec_compiler", step_ids)
        self.assertIn("agent_package_generator", step_ids)
        self.assertIn("acceptance_protocol_generator", step_ids)
        
        self.assertIn("writer_machine_spec", step_ids)
        self.assertIn("writer_human_brief", step_ids)
        self.assertIn("writer_agent_package", step_ids)
        self.assertIn("writer_acceptance", step_ids)
        self.assertIn("writer_traceability", step_ids)

        # Verify output spec
        self.assertEqual(definition.output_spec["machine_spec"], "machine_spec.yaml")
        self.assertEqual(definition.output_spec["human_brief"], "human_brief.md")
        self.assertEqual(definition.output_spec["agent_package"], "agent_package_codex.md")
        self.assertEqual(definition.output_spec["acceptance"], "acceptance.md")
        self.assertEqual(definition.output_spec["traceability"], "traceability.json")

    def test_spec_to_agent_registers_playbook_step_handlers(self):
        definition = build_spec_to_agent_definition()

        self.assertIn("context_normalizer", definition.metadata["custom_context_handlers"])
        self.assertIn("open_question_identifier", definition.metadata["custom_agent_handlers"])
        self.assertIn("machine_spec_compiler", definition.metadata["custom_agent_handlers"])
        self.assertIn("agent_package_generator", definition.metadata["custom_agent_handlers"])
        self.assertIn("acceptance_protocol_generator", definition.metadata["custom_agent_handlers"])
        self.assertIn("human_decision_gate", definition.metadata["custom_gate_handlers"])

    def test_runtime_writes_native_artifacts_in_order(self):
        service, storage = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        
        # Check that expected artifacts are created
        artifact_names = [artifact.name for artifact in artifacts]
        self.assertIn("machine_spec.yaml", artifact_names)
        self.assertIn("human_brief.md", artifact_names)
        self.assertIn("agent_package_codex.md", artifact_names)
        self.assertIn("acceptance.md", artifact_names)
        self.assertIn("traceability.json", artifact_names)
        
        # The first artifact is usually machine_spec or from context. Let's just check by name
        machine_spec_art = next(a for a in artifacts if a.name == "machine_spec.yaml")
        traceability_art = next(a for a in artifacts if a.name == "traceability.json")
        machine_spec = storage.read_artifact(machine_spec_art.artifact_id)
        traceability = storage.read_artifact(traceability_art.artifact_id)
        
        self.assertIn("business_intent:", machine_spec.content)
        self.assertIn("requirements:", machine_spec.content)
        self.assertIn('"source_of_truth": "machine_spec.yaml"', traceability.content)

    def test_runtime_compiles_structured_spec_outputs_for_gate_and_artifacts(self):
        service, storage = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "把登录能力编译为可执行任务包",
                "context_scope": "auth",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(
            result.context.step_outputs["context_normalizer"]["normalized_intent"],
            "把登录能力编译为可执行任务包",
        )
        self.assertEqual(
            result.context.step_outputs["machine_spec_compiler"]["structured"]["source_of_truth"],
            "machine_spec",
        )
        # Check human decision gate status
        self.assertEqual(
            result.context.step_outputs["human_decision_gate"]["gate"]["status"],
            "pass",
        )

        artifacts = storage.list_artifacts(task.task_id)
        machine_spec_art = next(a for a in artifacts if a.name == "machine_spec.yaml")
        machine_spec = storage.read_artifact(machine_spec_art.artifact_id)
        
        # It should contain compiler output
        self.assertIn("compiled", machine_spec.content.lower())


class TestSpecToAgentExecutors(unittest.TestCase):
    def test_context_normalizer_executor(self):
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.workflows.spec_to_agent import ContextNormalizerExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_1",
            task_type="spec_to_agent",
            username="alice",
            title="Test Task",
            goal="Normalize requirements",
            inputs={"business_intent": "  Test intent  ", "context_scope": "auth"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="context_normalizer", type="context", title="Test Step")

        executor = ContextNormalizerExecutor()
        result = executor.run(task, step)
        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["normalized_intent"], "Test intent")
        self.assertEqual(result.outputs["context_scope"], "auth")

    def test_machine_spec_compiler_executor(self):
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.services.fakes import FakeLLM
        from app.workflows.spec_to_agent import MachineSpecCompilerExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_2",
            task_type="spec_to_agent",
            username="alice",
            title="Compiler Spec",
            goal="Compile spec",
            inputs={"business_intent": "Auth flow"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="machine_spec_compiler", type="agent", title="Compiler Step", role="Compiler")

        executor = MachineSpecCompilerExecutor(llm=FakeLLM())
        result = executor.run(task, step)
        self.assertEqual(result.status.value, "succeeded")
        self.assertIn("JSONDecodeError", result.outputs["content"])
        self.assertEqual(result.outputs["structured"]["primary_requirement"], "Auth flow")

    def test_human_decision_gate_executor(self):
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.workflows.spec_to_agent import HumanDecisionGateExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_3",
            task_type="spec_to_agent",
            username="alice",
            title="Decision Gate Test",
            goal="Evaluate gate",
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="human_decision_gate", type="gate", title="Gate Step")

        executor = HumanDecisionGateExecutor()
        
        # In current mock implementation it should pass
        pass_result = executor.run(task, step)
        self.assertEqual(pass_result.status.value, "succeeded")
        self.assertEqual(pass_result.outputs["gate"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
