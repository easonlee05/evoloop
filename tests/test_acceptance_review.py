import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.task import TaskStatus
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.core.review import ReviewResult, ReviewVerdict
from app.workflows.acceptance_review import (
    build_acceptance_review_definition,
    serialize_review_result,
    verify_and_update_artifact_graph,
    DiffImpactAnalyzerExecutor,
)


class TestAcceptanceReviewWorkflow(unittest.TestCase):
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

    def test_acceptance_review_definition_structure(self):
        definition = build_acceptance_review_definition()
        self.assertEqual(definition.type, "acceptance_review")
        self.assertEqual(definition.metadata["is_native_3_0"], True)
        self.assertEqual(definition.metadata["source_of_truth"], "machine_spec")
        self.assertIn("ingest_acceptance_context", definition.metadata["custom_context_handlers"])
        self.assertIn("requirement_coverage", definition.metadata["custom_agent_handlers"])
        self.assertIn("diff_impact_analyzer", definition.metadata["custom_agent_handlers"])
        self.assertIn("review_result_compiler", definition.metadata["custom_agent_handlers"])
        self.assertIn("review_gate", definition.metadata["custom_gate_handlers"])

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # Verify core steps
        self.assertIn("ingest_acceptance_context", step_ids)
        self.assertIn("requirement_coverage", step_ids)
        self.assertIn("diff_impact_analyzer", step_ids)
        self.assertIn("review_result_compiler", step_ids)
        self.assertIn("review_gate", step_ids)
        self.assertIn("writer_review_result", step_ids)
        self.assertIn("final_checkpoint", step_ids)

        # Verify output spec
        self.assertEqual(definition.output_spec["review_result"], "review_result.md")

    def test_runtime_writes_review_result_artifact_for_pass_and_validates_graph(self):
        service, storage = self.make_service()
        task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login: 用户必须能使用手机号登录",
                "acceptance_protocol": "case_login: 输入手机号后应登录成功",
                "implementation_summary": "已完成手机号登录接口与页面联调",
                "diff": "+ add phone login flow",
            },
        )

        with patch("app.workflows.acceptance_review.verify_and_update_artifact_graph", wraps=verify_and_update_artifact_graph) as graph_helper:
            result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(graph_helper.call_count, 1)
        artifacts = storage.list_artifacts(task.task_id)
        self.assertEqual([artifact.name for artifact in artifacts], ["review_result.md"])
        review_result = storage.read_artifact(artifacts[0].artifact_id)
        # Since ReviewResult generates a random ID, we don't do full string compare.
        # Just check the presence of essential data.
        self.assertIn("Verdict: pass", review_result.content)
        self.assertIn("All checks passed.", review_result.content)
        self.assertIn("req_login", review_result.content)
        self.assertEqual(result.context.step_outputs["ingest_acceptance_context"]["requirement_ids"], ["req_login"])
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["review_verdict"], "pass")
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["issue_count"], 0)

    def test_runtime_writes_review_result_artifact_for_changes_required(self):
        service, storage = self.make_service()
        task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login: 用户必须能使用手机号登录",
                "acceptance_protocol": "case_login: 输入手机号后应登录成功",
                "implementation_summary": "登录流程基本完成但还有 missing edge case",
                "diff": "+ // TODO: 手机号格式校验暂未实现",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        review_result = storage.read_artifact(artifacts[0].artifact_id)
        self.assertIn("Verdict: changes_required", review_result.content)
        self.assertIn("Address issues: 存在未完成的 TODO 开发项", review_result.content)
        self.assertIn("Detected issues: 存在未完成的 TODO 开发项", review_result.content)
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["review_verdict"], "changes_required")
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["issue_count"], 1)
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["coverage_count"], 1)

    def test_diff_impact_analyzer_failure_cases(self):
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        
        context = TaskContext(
            task_id="task_exec_diff",
            task_type="acceptance_review",
            username="alice",
            title="Test Diff",
            goal="Diff Test",
            inputs={"diff": "+ // TODO: 手机号格式校验暂未实现", "implementation_summary": "登录功能已基本实现", "machine_spec": "req_login:"},
        )
        # Pretend ingest_acceptance_context already ran
        context.step_outputs["ingest_acceptance_context"] = {
            "diff": "+ // TODO: 手机号格式校验暂未实现",
            "implementation_summary": "登录功能已基本实现",
            "requirement_ids": ["req_login"]
        }
        
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="diff_impact_analyzer", type="agent", title="Diff Check")
        
        agent = DiffImpactAnalyzerExecutor()

        # 模拟含有 TODO 缺陷的变更
        fail_result = agent.run(task, step)
        
        self.assertEqual(fail_result.status.value, "succeeded")
        self.assertEqual(len(fail_result.outputs["issues"]), 1)
        self.assertEqual(fail_result.outputs["issues"][0]["severity"], "major")
        self.assertEqual(len(fail_result.outputs["fix_tasks"]), 1)
        self.assertIn("req_login", fail_result.outputs["issues"][0]["related_requirement_ids"])

    def test_graph_validation(self):
        # 验证图关系回写与 validate
        graph = verify_and_update_artifact_graph(
            work_id="work_123",
            machine_spec_ref="memory://tasks/work_123/machine_spec",
            review_result_ref="file://artifacts/review_result_123.md",
            acceptance_protocol_ref="memory://tasks/work_123/acceptance_protocol",
        )
        # validate() should pass without raising ArtifactGraphValidationError
        graph.validate()

if __name__ == "__main__":
    unittest.main()
