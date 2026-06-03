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
    AdversarialVerificationAgent,
    build_acceptance_review_definition,
    serialize_review_result,
    verify_and_update_artifact_graph,
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

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # Verify core steps
        self.assertIn("ingest_acceptance_context", step_ids)
        self.assertIn("adversarial_verify", step_ids)
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
        structured_review = result.context.step_outputs["adversarial_verify"]["review_result"]
        self.assertEqual(review_result.content, serialize_review_result(ReviewResult.from_dict(structured_review)))
        self.assertIn("Verdict: pass", review_result.content)
        self.assertIn("Adversarial check complete. All green.", review_result.content)
        self.assertIn("Review ID:", review_result.content)
        self.assertIn("req_login", review_result.content)

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
        structured_review = result.context.step_outputs["adversarial_verify"]["review_result"]
        self.assertEqual(review_result.content, serialize_review_result(ReviewResult.from_dict(structured_review)))
        self.assertIn("Verdict: changes_required", review_result.content)
        self.assertIn("Address adversarial review issues", review_result.content)
        self.assertIn("Detected logic gap or missing implementation in diff", review_result.content)

    def test_adversarial_verification_and_graph_validation(self):
        agent = AdversarialVerificationAgent(
            work_id="work_123",
            machine_spec_ref="memory://tasks/work_123/machine_spec",
            acceptance_protocol_ref="memory://tasks/work_123/acceptance_protocol",
        )

        # 模拟通过的交付
        success_result = agent.verify(
            machine_spec="req_1: 必须实现 A 接口",
            acceptance_protocol="case_1: 验证 A 接口返回 200",
            implementation_summary="实现了 A 接口，测试通过",
            diff="+ def test_a(): pass",
        )
        self.assertEqual(success_result.verdict, ReviewVerdict.PASS)
        self.assertTrue(all(cov.covered for cov in success_result.coverage))

        # 验证图关系回写与 validate
        graph = verify_and_update_artifact_graph(
            work_id="work_123",
            machine_spec_ref="memory://tasks/work_123/machine_spec",
            review_result_ref="file://artifacts/review_result_123.md",
            acceptance_protocol_ref="memory://tasks/work_123/acceptance_protocol",
        )
        # validate() should pass without raising ArtifactGraphValidationError
        graph.validate()

    def test_adversarial_verification_failure_cases(self):
        from app.core.review import ReviewIssueSeverity
        agent = AdversarialVerificationAgent(
            work_id="work_456",
            machine_spec_ref="memory://tasks/work_456/machine_spec"
        )

        # 模拟含有 TODO 缺陷的变更
        fail_result = agent.verify(
            machine_spec="req_login: 用户必须能使用手机号登录",
            acceptance_protocol="case_login: 输入手机号，验证成功登录",
            implementation_summary="登录功能已基本实现",
            diff="+ // TODO: 手机号格式校验暂未实现"
        )
        self.assertEqual(fail_result.verdict, ReviewVerdict.CHANGES_REQUIRED)
        self.assertEqual(len(fail_result.issues), 1)
        self.assertEqual(fail_result.issues[0].severity, ReviewIssueSeverity.MAJOR)
        self.assertEqual(len(fail_result.fix_tasks), 1)
        self.assertIn("req_login", fail_result.issues[0].related_requirement_ids)

        # 验证序列化格式
        serialized = serialize_review_result(fail_result)
        self.assertIn("# Acceptance Review Result", serialized)
        self.assertIn("Verdict: changes_required", serialized)
        self.assertIn("req_login", serialized)
        self.assertIn("Address adversarial review issues", serialized)


if __name__ == "__main__":
    unittest.main()
