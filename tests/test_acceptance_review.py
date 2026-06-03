import unittest

# This should fail initially because acceptance_review module doesn't exist yet
from app.workflows.acceptance_review import (
    build_acceptance_review_definition,
    AdversarialVerificationAgent,
    verify_and_update_artifact_graph,
)
from app.core.review import ReviewVerdict


class TestAcceptanceReviewWorkflow(unittest.TestCase):
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
        self.assertIn("writer_scene_docs", step_ids)
        self.assertIn("final_checkpoint", step_ids)

        # Verify output spec
        self.assertEqual(definition.output_spec["review_result"], "review_result.md")

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
        from app.workflows.acceptance_review import serialize_review_result

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
