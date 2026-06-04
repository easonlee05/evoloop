"""Legacy PRD TaskDefinition built on the generic workflow engine."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.task import StepResult, StepStatus, Task, TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.policies import build_default_tool_policy


def _convergence_dispute_package(task: Task, round_count: int) -> Dict[str, Any]:
    return {
        "title": "多轮评审后仍未收敛",
        "background": task.context.goal,
        "decision_needed": f"Tech 与 QA 在第 {round_count} 轮后仍有实质分歧，需要你决定这版 PRD 先按哪种取舍继续推进。",
        "options": [
            {
                "label": "A",
                "pm_position": "优先交付，接受可控风险，先保证本期落地。",
                "tech_position": "保留部分技术债，后续再补架构增强。",
                "qa_position": "异常路径先覆盖高风险部分，降低当前返工成本。",
                "benefit": "更快交付",
                "cost": "后续补强",
                "risk": "残留部分稳健性风险",
                "recommended": False,
            },
            {
                "label": "B",
                "pm_position": "优先稳健，先补齐关键风险控制和异常闭环。",
                "tech_position": "允许当前版本延后，以换取更稳定的方案边界。",
                "qa_position": "把主要异常与验收条件补完整后再进入终稿。",
                "benefit": "方案更稳",
                "cost": "交付变慢",
                "risk": "首期范围可能缩小",
                "recommended": True,
            },
        ],
        "impact_after_decision": "PM 将按你的取舍重写方案，再进入最终文档产出阶段。",
    }


def convergence_gate_step(task: Task, step: WorkflowStep, llm: Any = None) -> StepResult:
    if task.context.user_decisions:
        gate = {"step_id": step.id, "status": "pass", "checks": task.definition.gate_policy.get("gates", [])}
        task.context.gate_results.append(gate)
        return StepResult(step.id, StepStatus.SUCCEEDED, "gate passed", outputs={"gate": gate})

    if task.context.inputs.get("force_arbitration") is not None:
        consensus_reached = not task.context.inputs.get("force_arbitration")
    else:
        consensus_reached = False
        if llm is not None:
            llm_context = {
                **task.context.inputs,
                "title": task.context.title,
                "goal": task.context.goal,
                "round_history": [
                    {"role": h["role"], "content": h["content"]}
                    for h in task.context.round_history
                ],
            }
            gate_prompt = "请作为严格的 Reviewer，评估历史记录中近期 Tech 和 QA 对 PM 方案的二审反馈。如果他们对方案基本认可且没有要求重大重构或修改（允许有轻微建议），请只回复“PASS”；如果存在未解决的严重异议或明确要求 PM 重新修改，请只回复“FAIL”。必须只回复这两个词之一。"
            try:
                result = llm.invoke("Reviewer", gate_prompt, llm_context)
                consensus_reached = (result.content or "").strip().upper() == "PASS"
            except Exception:
                consensus_reached = False

    if not consensus_reached:
        max_rounds = task.definition.round_policy.get("max_rounds", 3)
        task.context.round_count += 1
        if task.context.round_count >= max_rounds:
            return StepResult(
                step.id,
                StepStatus.NEEDS_ARBITRATION,
                f"convergence requires human arbitration (max rounds {max_rounds} reached)",
                outputs={"dispute_package": _convergence_dispute_package(task, task.context.round_count)},
                next_step_id="arbitration_business_tradeoff",
                resume_step_id="pm_after_arbitration",
            )
        gate = {"step_id": step.id, "status": "fail", "round": task.context.round_count}
        task.context.gate_results.append(gate)
        return StepResult(
            step.id,
            StepStatus.SUCCEEDED,
            f"convergence failed, looping back. Round {task.context.round_count}",
            outputs={"gate": gate},
            next_step_id="pm_first_draft",
        )

    gate = {"step_id": step.id, "status": "pass", "checks": task.definition.gate_policy.get("gates", [])}
    task.context.gate_results.append(gate)
    return StepResult(step.id, StepStatus.SUCCEEDED, "gate passed", outputs={"gate": gate})


def arbitration_business_tradeoff_step(task: Task, step: WorkflowStep) -> StepResult:
    if not task.context.inputs.get("force_arbitration") or task.context.user_decisions:
        return StepResult(step.id, StepStatus.SUCCEEDED, "arbitration skipped", outputs={})
    dispute_package = {
        "title": "业务取舍需要裁决",
        "background": task.context.goal,
        "decision_needed": "请选择一致性、性能和交付速度之间的首期取舍。",
        "options": [
            {"label": "A", "pm_position": "同步强一致", "tech_position": "成本较高", "qa_position": "异常更少", "benefit": "结果确定", "cost": "性能成本", "risk": "发布慢", "recommended": False},
            {"label": "B", "pm_position": "异步加对账", "tech_position": "解耦更好", "qa_position": "需补偿机制", "benefit": "易交付", "cost": "短时不一致", "risk": "需审计", "recommended": True},
        ],
        "impact_after_decision": "PM 将按用户裁决重写主流程、风险和验收标准。",
    }
    return StepResult(
        step.id,
        StepStatus.NEEDS_ARBITRATION,
        "waiting for user decision",
        outputs={"dispute_package": dispute_package},
        resume_step_id=step.pause_policy.get("resume_step_id"),
    )


def writer_final_prd_step(
    task: Task,
    step: WorkflowStep,
    llm=None,
    content: Optional[str] = None,
    context_compiler: Optional[ContextCompilerService] = None,
) -> StepResult:
    compiler = context_compiler or ContextCompilerService()
    body = content or f"Writer final PRD for {task.context.title}"
    artifact_content = body if ("背景" in body and "业务目标" in body) else compiler.render_prd(task)
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        f"{step.role} completed",
        outputs={
            "content": body,
            "structured": {"role": step.role, "title": task.context.title, "goal": task.context.goal},
            "artifact_name": "PRD.md",
            "artifact_content": artifact_content,
        },
    )


def build_prd_definition(public_task_type: str = "legacy_prd") -> TaskDefinition:
    workflow = WorkflowSpec(
        name="legacy_prd.minimum.v1",
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
        display_name="Legacy PRD 投影",
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
        metadata={
            "legacy_bridge": True,
            "legacy_playbook_id": public_task_type,
            "canonical_task_type": "prd",
            "public_task_type": public_task_type,
            "legacy_projection": "optional_prd",
            "legacy_aliases": [public_task_type, "prd"],
            "custom_gate_handlers": {
                "convergence_gate": convergence_gate_step,
            },
            "custom_arbitration_handlers": {
                "arbitration_business_tradeoff": arbitration_business_tradeoff_step,
            },
            "custom_agent_handlers": {
                "writer_final_prd": writer_final_prd_step,
            },
        },
    )
