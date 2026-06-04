import unittest

from app.core.context import TaskContext, UserDecision
from app.core.ports import LLMResult
from app.core.task import StepStatus, Task
from app.workflows.prd import (
    arbitration_business_tradeoff_step,
    build_prd_definition,
    convergence_gate_step,
)


class _FailReviewerLLM:
    def invoke(self, role, prompt, context):
        if role == "Reviewer":
            return LLMResult(content="FAIL", structured={"role": role})
        return LLMResult(content=f"{role} ok", structured={"role": role})


class _PassReviewerLLM:
    def invoke(self, role, prompt, context):
        if role == "Reviewer":
            return LLMResult(content="PASS", structured={"role": role})
        return LLMResult(content=f"{role} ok", structured={"role": role})


class PRDPlaybookHandlerTests(unittest.TestCase):
    def make_task(self, **inputs):
        definition = build_prd_definition()
        context = TaskContext(
            task_id="task_prd",
            task_type="prd",
            username="alice",
            goal=inputs.get("business_goal", "降低发布风险"),
            title=inputs.get("feature", "灰度发布"),
            inputs={
                "feature": inputs.get("feature", "灰度发布"),
                "business_goal": inputs.get("business_goal", "降低发布风险"),
                **inputs,
            },
        )
        return Task(definition=definition, context=context, task_id="task_prd")

    def test_prd_registers_custom_playbook_handlers(self):
        definition = build_prd_definition()

        self.assertIn("convergence_gate", definition.metadata["custom_gate_handlers"])
        self.assertIn("arbitration_business_tradeoff", definition.metadata["custom_arbitration_handlers"])

    def test_convergence_gate_loops_back_before_max_rounds(self):
        task = self.make_task()
        task.definition.round_policy["max_rounds"] = 3
        step = next(step for step in task.definition.workflow.steps if step.id == "convergence_gate")

        result = convergence_gate_step(task, step, llm=_FailReviewerLLM())

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.next_step_id, "pm_first_draft")
        self.assertEqual(result.outputs["gate"]["status"], "fail")
        self.assertEqual(result.outputs["gate"]["round"], 1)
        self.assertEqual(task.context.round_count, 1)

    def test_convergence_gate_requests_arbitration_after_max_rounds(self):
        task = self.make_task()
        task.definition.round_policy["max_rounds"] = 1
        step = next(step for step in task.definition.workflow.steps if step.id == "convergence_gate")

        result = convergence_gate_step(task, step, llm=_FailReviewerLLM())

        self.assertEqual(result.status, StepStatus.NEEDS_ARBITRATION)
        self.assertEqual(result.next_step_id, "arbitration_business_tradeoff")
        self.assertEqual(result.resume_step_id, "pm_after_arbitration")
        self.assertIn("options", result.outputs["dispute_package"])

    def test_convergence_gate_passes_after_user_decision_exists(self):
        task = self.make_task(force_arbitration=True)
        task.context.user_decisions.append(UserDecision(decision="按方案 B 执行", selected_option="B"))
        step = next(step for step in task.definition.workflow.steps if step.id == "convergence_gate")

        result = convergence_gate_step(task, step, llm=_FailReviewerLLM())

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.outputs["gate"]["status"], "pass")
        self.assertIn("目标一致性", result.outputs["gate"]["checks"])

    def test_arbitration_step_returns_dispute_package_when_forced(self):
        task = self.make_task(force_arbitration=True)
        step = next(step for step in task.definition.workflow.steps if step.id == "arbitration_business_tradeoff")

        result = arbitration_business_tradeoff_step(task, step)

        self.assertEqual(result.status, StepStatus.NEEDS_ARBITRATION)
        self.assertEqual(result.resume_step_id, "pm_after_arbitration")
        self.assertEqual(result.outputs["dispute_package"]["options"][1]["label"], "B")

    def test_arbitration_step_skips_after_decision(self):
        task = self.make_task(force_arbitration=True)
        task.context.user_decisions.append(UserDecision(decision="采用方案 A", selected_option="A"))
        step = next(step for step in task.definition.workflow.steps if step.id == "arbitration_business_tradeoff")

        result = arbitration_business_tradeoff_step(task, step)

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.summary, "arbitration skipped")


if __name__ == "__main__":
    unittest.main()
