"""Native Spec-to-Agent TaskDefinition built on the generic workflow engine."""
from __future__ import annotations

from typing import Any, Dict

from app.core.task import StepResult, StepStatus, Task, TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_default_tool_policy


def _spec_inputs(task: Task) -> Dict[str, Any]:
    normalized_intent = str(task.context.inputs.get("business_intent") or task.context.goal).strip()
    context_scope = str(task.context.inputs.get("context_scope") or "default").strip()
    constraints = [str(item) for item in task.context.user_constraints or task.context.inputs.get("constraints", [])]
    return {
        "normalized_intent": normalized_intent,
        "context_scope": context_scope or "default",
        "constraints": constraints,
    }


def ingest_requirements_step(task: Task, step: WorkflowStep) -> StepResult:
    inputs = _spec_inputs(task)
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        "requirements normalized",
        outputs=inputs,
    )


def pm_draft_machine_spec_step(task: Task, step: WorkflowStep, llm: Any = None) -> StepResult:
    inputs = _spec_inputs(task)
    content = f"PM machine spec draft for {task.context.title}: {inputs['normalized_intent']}"
    if llm is not None:
        response = llm.invoke(
            step.role,
            step.title,
            {
                "title": task.context.title,
                "goal": task.context.goal,
                "business_intent": inputs["normalized_intent"],
                "context_scope": inputs["context_scope"],
            },
        )
        content = response.content
    structured = {
        "source_of_truth": "machine_spec",
        "primary_requirement": inputs["normalized_intent"],
        "context_scope": inputs["context_scope"],
        "constraints": inputs["constraints"],
    }
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        "machine spec drafted",
        outputs={"content": content, "structured": structured},
    )


def tech_review_spec_step(task: Task, step: WorkflowStep, llm: Any = None) -> StepResult:
    inputs = _spec_inputs(task)
    content = f"Tech review for {task.context.title}: architecture feasible"
    if llm is not None:
        response = llm.invoke(
            step.role,
            step.title,
            {
                "title": task.context.title,
                "goal": task.context.goal,
                "business_intent": inputs["normalized_intent"],
            },
        )
        content = response.content
    structured = {
        "technical_review": "architecture feasible",
        "focus": ["dependencies", "integration", "rollback"],
        "context_scope": inputs["context_scope"],
    }
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        "technical review completed",
        outputs={"content": content, "structured": structured},
    )


def qa_draft_acceptance_step(task: Task, step: WorkflowStep, llm: Any = None) -> StepResult:
    inputs = _spec_inputs(task)
    content = f"QA acceptance draft for {task.context.title}: cover happy path and failures"
    if llm is not None:
        response = llm.invoke(
            step.role,
            step.title,
            {
                "title": task.context.title,
                "goal": task.context.goal,
                "business_intent": inputs["normalized_intent"],
            },
        )
        content = response.content
    structured = {
        "acceptance_inputs": [
            "Trace to machine_spec requirement",
            "Validate downstream worker package",
            "Verify acceptance protocol coverage",
        ],
        "critical_checks": ["happy_path", "error_path", "traceability"],
    }
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        "acceptance draft completed",
        outputs={"content": content, "structured": structured},
    )


def spec_gate_step(task: Task, step: WorkflowStep) -> StepResult:
    evidence_step_ids = ["pm_draft_machine_spec", "tech_review_spec", "qa_draft_acceptance"]
    missing = [step_id for step_id in evidence_step_ids if step_id not in task.context.step_outputs]
    if missing:
        return StepResult(
            step.id,
            StepStatus.FAILED,
            error=None,
            summary="spec gate missing evidence",
            outputs={"gate": {"step_id": step.id, "status": "fail", "missing_evidence": missing}},
        )
    gate = {
        "step_id": step.id,
        "status": "pass",
        "checks": task.definition.gate_policy.get("gates", []),
        "evidence_step_ids": evidence_step_ids,
    }
    task.context.gate_results.append(gate)
    return StepResult(step.id, StepStatus.SUCCEEDED, "spec gate passed", outputs={"gate": gate})


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
            "source_of_truth": "machine_spec.yaml",
            "custom_context_handlers": {
                "ingest_requirements": ingest_requirements_step,
            },
            "custom_agent_handlers": {
                "pm_draft_machine_spec": pm_draft_machine_spec_step,
                "tech_review_spec": tech_review_spec_step,
                "qa_draft_acceptance": qa_draft_acceptance_step,
            },
            "custom_gate_handlers": {
                "spec_gate": spec_gate_step,
            },
        },
    )
