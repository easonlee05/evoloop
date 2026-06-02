"""PRD TaskDefinition built on the generic workflow engine."""
from __future__ import annotations

from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_default_tool_policy


def build_prd_definition() -> TaskDefinition:
    workflow = WorkflowSpec(
        name="prd.minimum.v1",
        version="1.0",
        steps=[
            WorkflowStep(id="build_context", type="context", title="构建 PRD 任务上下文"),
            WorkflowStep(
                id="retrieve_knowledge",
                type="context",
                title="检索知识上下文",
                allowed_tools=["knowledge.retrieve"],
            ),
            WorkflowStep(id="pm_draft", type="agent", title="PM 输出 PRD 草案", role="PM"),
            WorkflowStep(id="tech_challenge", type="agent", title="Tech 评估可行性与风险", role="Tech", parallel_group="reviewers_draft"),
            WorkflowStep(id="qa_challenge", type="agent", title="QA 评估异常与边缘场景", role="QA", parallel_group="reviewers_draft"),
            WorkflowStep(id="pm_first_draft", type="agent", title="PM 输出 PRD 初稿", role="PM"),
            WorkflowStep(id="tech_review", type="agent", title="Tech 二审 PRD 初稿", role="Tech", parallel_group="reviewers_first_draft"),
            WorkflowStep(id="qa_review", type="agent", title="QA 二审 PRD 初稿", role="QA", parallel_group="reviewers_first_draft"),
            WorkflowStep(id="convergence_gate", type="gate", title="收敛门禁", role="Reviewer"),
            WorkflowStep(
                id="arbitration_business_tradeoff",
                type="arbitration",
                title="业务取舍仲裁",
                role="SYSTEM",
                pause_policy={"resume_step_id": "pm_after_arbitration"},
            ),
            WorkflowStep(id="pm_after_arbitration", type="agent", title="PM 吸收用户裁决", role="PM"),
            WorkflowStep(id="reviewer_gate", type="gate", title="Reviewer 质量门禁", role="Reviewer"),
            WorkflowStep(id="writer_final_prd", type="agent", title="Writer 输出最终 PRD", role="Writer"),
            WorkflowStep(
                id="write_prd_artifact",
                type="artifact",
                title="写入 PRD 产物",
                role="Writer",
                allowed_tools=["artifact.write"],
            ),
            WorkflowStep(id="final_checkpoint", type="checkpoint", title="保存最终 checkpoint"),
        ],
    )
    return TaskDefinition(
        type="prd",
        display_name="PRD 编写",
        input_schema={
            "required": ["username", "feature", "business_goal"],
            "properties": {
                "username": {"type": "string"},
                "feature": {"type": "string"},
                "business_goal": {"type": "string"},
                "constraints": {"type": "array"},
                "preferences": {"type": "array"},
                "material_ids": {"type": "array"},
                "force_arbitration": {"type": "boolean"},
            },
        },
        workflow=workflow,
        tool_policy=build_default_tool_policy("prd"),
        agents={"pm": "PM", "tech": "Tech", "qa": "QA", "reviewer": "Reviewer", "writer": "Writer"},
        round_policy={"max_rounds": 3},
        gate_policy={"gates": ["目标一致性", "架构完整性", "异常完整性", "风险透明度", "可交付性"]},
        output_spec={"primary_artifact": "PRD.md"},
    )
