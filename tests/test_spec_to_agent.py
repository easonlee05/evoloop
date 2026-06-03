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
        self.assertIn("ingest_requirements", step_ids)
        self.assertIn("pm_draft_machine_spec", step_ids)
        self.assertIn("writer_machine_spec", step_ids)
        self.assertIn("writer_human_brief", step_ids)
        self.assertIn("writer_agent_package", step_ids)
        self.assertIn("writer_acceptance", step_ids)
        self.assertIn("writer_review_checklist", step_ids)
        self.assertIn("writer_traceability", step_ids)

        # Verify output spec
        self.assertEqual(definition.output_spec["machine_spec"], "machine_spec.yaml")
        self.assertEqual(definition.output_spec["human_brief"], "human_brief.md")
        self.assertEqual(definition.output_spec["agent_package"], "agent_package_codex.md")
        self.assertEqual(definition.output_spec["acceptance"], "acceptance.md")
        self.assertEqual(definition.output_spec["review_checklist"], "review_checklist.md")
        self.assertEqual(definition.output_spec["traceability"], "traceability.json")

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
        self.assertEqual(
            [artifact.name for artifact in artifacts],
            [
                "machine_spec.yaml",
                "human_brief.md",
                "agent_package_codex.md",
                "acceptance.md",
                "review_checklist.md",
                "traceability.json",
            ],
        )
        machine_spec = storage.read_artifact(artifacts[0].artifact_id)
        traceability = storage.read_artifact(artifacts[-1].artifact_id)
        self.assertIn("business_intent:", machine_spec.content)
        self.assertIn("requirements:", machine_spec.content)
        self.assertIn('"source_of_truth": "machine_spec.yaml"', traceability.content)


if __name__ == "__main__":
    unittest.main()
