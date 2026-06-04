import unittest

from app.core.context import TaskContext
from app.core.task import Task
from app.workflows.manual import (
    build_manual_definition,
    writer_overview_step,
    writer_scene_docs_step,
)
from app.workflows.prd import build_prd_definition, writer_final_prd_step
from app.workflows.context_compiler import ContextCompilerService


class ManualAndWriterHandlerTests(unittest.TestCase):
    def make_manual_task(self, **inputs):
        definition = build_manual_definition()
        context = TaskContext(
            task_id="task_manual",
            task_type="manual",
            username="alice",
            goal=inputs.get("instructions", "补全模块操作说明"),
            title=inputs.get("module_name", "订单中心"),
            inputs={
                "module_name": inputs.get("module_name", "订单中心"),
                "instructions": inputs.get("instructions", "补全模块操作说明"),
                **inputs,
            },
        )
        return Task(definition=definition, context=context, task_id="task_manual")

    def make_prd_task(self, **inputs):
        definition = build_prd_definition()
        context = TaskContext(
            task_id="task_prd",
            task_type="prd",
            username="alice",
            goal=inputs.get("business_goal", "降低异常积分套利"),
            title=inputs.get("feature", "积分防刷网关"),
            inputs={
                "feature": inputs.get("feature", "积分防刷网关"),
                "business_goal": inputs.get("business_goal", "降低异常积分套利"),
                **inputs,
            },
        )
        return Task(definition=definition, context=context, task_id="task_prd")

    def test_manual_registers_writer_handlers(self):
        definition = build_manual_definition()

        self.assertIn("writer_overview", definition.metadata["custom_agent_handlers"])
        self.assertIn("writer_scene_docs", definition.metadata["custom_agent_handlers"])

    def test_prd_registers_writer_handler(self):
        definition = build_prd_definition()

        self.assertIn("writer_final_prd", definition.metadata["custom_agent_handlers"])

    def test_manual_writer_overview_falls_back_to_rendered_manual(self):
        task = self.make_manual_task()
        step = next(step for step in task.definition.workflow.steps if step.id == "writer_overview")

        result = writer_overview_step(task, step, context_compiler=ContextCompilerService())

        self.assertEqual(result.outputs["artifact_name"], "模块概览.md")
        self.assertIn("操作手册", result.outputs["artifact_content"])

    def test_manual_writer_scene_docs_keeps_rich_manual_content(self):
        task = self.make_manual_task()
        step = next(step for step in task.definition.workflow.steps if step.id == "writer_scene_docs")

        result = writer_scene_docs_step(
            task,
            step,
            content="这里是详细操作路径\n1. 打开页面\n2. 提交审批\n3. 查看结果",
            context_compiler=ContextCompilerService(),
        )

        self.assertIn("操作路径", result.outputs["artifact_content"])
        self.assertEqual(result.outputs["artifact_name"], "模块概览.md")

    def test_prd_writer_falls_back_to_rendered_prd_when_content_is_not_structured(self):
        task = self.make_prd_task()
        step = next(step for step in task.definition.workflow.steps if step.id == "writer_final_prd")

        result = writer_final_prd_step(task, step, content="Writer response only", context_compiler=ContextCompilerService())

        self.assertEqual(result.outputs["artifact_name"], "PRD.md")
        self.assertIn("## 1. 背景与问题定义", result.outputs["artifact_content"])


if __name__ == "__main__":
    unittest.main()
