"""Native Spec-to-Agent TaskDefinition built on the generic workflow engine."""
from __future__ import annotations

from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_default_tool_policy


def build_spec_to_agent_definition(public_task_type: str = "spec_to_agent") -> TaskDefinition:
    workflow = WorkflowSpec(
        name="spec_to_agent.lane.v1",
        version="1.0",
        steps=[
            WorkflowStep(id="ingest_requirements", type="context", title="解析业务需求与上下文", allowed_tools=["material.parse"]),
            WorkflowStep(id="pm_draft_machine_spec", type="agent", title="PM 起草 Machine Spec (真相源)", role="PM"),
            WorkflowStep(id="tech_review_spec", type="agent", title="Tech 审查架构可行性", role="Tech", parallel_group="reviewers"),
            WorkflowStep(id="qa_draft_acceptance", type="agent", title="QA 起草验收协议与红线", role="QA", parallel_group="reviewers"),
            WorkflowStep(id="spec_gate", type="gate", title="Reviewer Spec 门禁", role="Reviewer"),
            WorkflowStep(id="writer_machine_spec", type="artifact", title="写入 machine_spec.yaml", role="Writer", allowed_tools=["artifact.write"], output_keys=["machine_spec"]),
            WorkflowStep(id="writer_human_brief", type="artifact", title="写入 human_brief.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["human_brief"]),
            WorkflowStep(id="writer_agent_package", type="artifact", title="写入 agent_package_codex.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["agent_package"]),
            WorkflowStep(id="writer_acceptance", type="artifact", title="写入 acceptance.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["acceptance"]),
            WorkflowStep(id="writer_review_checklist", type="artifact", title="写入 review_checklist.md", role="Writer", allowed_tools=["artifact.write"], output_keys=["review_checklist"]),
            WorkflowStep(id="writer_traceability", type="artifact", title="写入 traceability.json", role="Writer", allowed_tools=["artifact.write"], output_keys=["traceability"]),
            WorkflowStep(id="final_checkpoint", type="checkpoint", title="保存最终 checkpoint"),
        ],
    )
    return TaskDefinition(
        type="spec_to_agent",
        display_name="Spec to Agent Playbook",
        input_schema={
            "required": ["username", "business_intent"],
            "properties": {
                "username": {"type": "string"},
                "business_intent": {"type": "string"},
                "material_ids": {"type": "array"},
                "context_scope": {"type": "string"},
            },
        },
        workflow=workflow,
        tool_policy=build_default_tool_policy("spec_to_agent"),
        agents={"pm": "PM", "tech": "Tech", "qa": "QA", "reviewer": "Reviewer", "writer": "Writer"},
        round_policy={"max_rounds": 3},
        gate_policy={"gates": ["Spec 完备性", "技术可行性", "测试可测性", "依赖无环"]},
        output_spec={
            "machine_spec": "machine_spec.yaml",
            "human_brief": "human_brief.md",
            "agent_package": "agent_package_codex.md",
            "acceptance": "acceptance.md",
            "review_checklist": "review_checklist.md",
            "traceability": "traceability.json"
        },
        metadata={
            "lane": "spec_to_agent",
            "canonical_task_type": "spec_to_agent",
            "public_task_type": public_task_type,
            "is_native_3_0": True,
            "source_of_truth": "machine_spec.yaml"
        },
    )
