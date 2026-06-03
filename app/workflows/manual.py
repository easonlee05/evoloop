"""Legacy manual TaskDefinition built on the generic workflow engine."""
from __future__ import annotations

from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_default_tool_policy


def build_manual_definition(public_task_type: str = "legacy_manual") -> TaskDefinition:
    workflow = WorkflowSpec(
        name="legacy_manual.skeleton.v1",
        version="1.0",
        steps=[
            WorkflowStep(id="ingest_materials", type="context", title="解析上传材料", allowed_tools=["material.parse"]),
            WorkflowStep(id="build_context", type="context", title="构建操作手册上下文"),
            WorkflowStep(id="retrieve_knowledge", type="context", title="检索平台知识", allowed_tools=["knowledge.retrieve"]),
            WorkflowStep(id="pm_outline_and_questions", type="agent", title="PM 识别模块目标与拆分方案", role="PM"),
            WorkflowStep(id="tech_fact_check", type="agent", title="Tech 校正技术事实", role="Tech", parallel_group="reviewers"),
            WorkflowStep(id="qa_operability_check", type="agent", title="QA 挑战可执行性", role="QA", parallel_group="reviewers"),
            WorkflowStep(id="reviewer_plan_gate", type="gate", title="Reviewer 方案门禁", role="Reviewer"),
            WorkflowStep(id="writer_overview", type="agent", title="Writer 输出模块概览", role="Writer"),
            WorkflowStep(id="writer_scene_docs", type="agent", title="Writer 输出操作场景文档", role="Writer"),
            WorkflowStep(id="reviewer_document_gate", type="gate", title="Reviewer 文档门禁", role="Reviewer"),
            WorkflowStep(id="write_manual_artifact", type="artifact", title="写入操作手册产物", role="Writer", allowed_tools=["artifact.write"]),
            WorkflowStep(id="final_checkpoint", type="checkpoint", title="保存最终 checkpoint"),
        ],
    )
    return TaskDefinition(
        type="manual",
        display_name="Legacy 操作手册投影",
        input_schema={
            "required": ["username", "module_name"],
            "properties": {
                "username": {"type": "string"},
                "module_name": {"type": "string"},
                "instructions": {"type": "string"},
                "material_ids": {"type": "array"},
                "knowledge_scope": {"type": "string"},
            },
        },
        workflow=workflow,
        tool_policy=build_default_tool_policy("manual"),
        agents={"pm": "PM", "tech": "Tech", "qa": "QA", "reviewer": "Reviewer", "writer": "Writer"},
        round_policy={"max_rounds": 3},
        gate_policy={"gates": ["格式红线", "材料映射", "去内部痕迹", "重复章节"]},
        output_spec={"primary_artifact": "模块概览.md"},
        metadata={
            "format_spec_asset": "app/格式.md",
            "legacy_bridge": True,
            "legacy_playbook_id": public_task_type,
            "canonical_task_type": "manual",
            "public_task_type": public_task_type,
            "legacy_projection": "optional_manual",
            "legacy_aliases": [public_task_type, "manual"],
        },
    )
