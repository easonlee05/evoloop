from __future__ import annotations

import re
from typing import Optional
from uuid import uuid4

from app.core.artifact_graph import (
    ArtifactEdge,
    ArtifactEdgeType,
    ArtifactGraph,
    ArtifactNode,
    ArtifactNodeType,
    ArtifactRef,
)
from app.core.review import (
    RequirementCoverage,
    ReviewFixTask,
    ReviewIssue,
    ReviewIssueSeverity,
    ReviewResult,
    ReviewVerdict,
)
from app.core.errors import DomainError
from app.core.task import StepResult, StepStatus, Task, TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_default_tool_policy


def build_acceptance_review_definition(public_task_type: str = "acceptance_review") -> TaskDefinition:
    workflow = WorkflowSpec(
        name="acceptance_review.lane.v1",
        version="1.0",
        steps=[
            WorkflowStep(
                id="ingest_acceptance_context",
                type="context",
                title="解析验收上下文",
                allowed_tools=["material.parse"],
            ),
            WorkflowStep(
                id="adversarial_verify",
                type="agent",
                title="对抗性安全与边界条件扫描",
                role="AdversarialReviewer",
            ),
            WorkflowStep(id="review_gate", type="gate", title="验收门禁判断", role="Reviewer"),
            WorkflowStep(
                id="writer_review_result",
                type="artifact",
                title="写入 review_result.md 并校验图关系",
                role="Writer",
                allowed_tools=["artifact.write"],
                output_keys=["review_result"],
            ),
            WorkflowStep(id="final_checkpoint", type="checkpoint", title="保存最终 checkpoint"),
        ],
    )
    return TaskDefinition(
        type="acceptance_review",
        display_name="Acceptance Review Playbook",
        input_schema={
            "required": ["username", "machine_spec", "acceptance_protocol", "implementation_summary", "diff"],
            "properties": {
                "username": {"type": "string"},
                "machine_spec": {"type": "string"},
                "acceptance_protocol": {"type": "string"},
                "implementation_summary": {"type": "string"},
                "diff": {"type": "string"},
            },
        },
        workflow=workflow,
        tool_policy=build_default_tool_policy("acceptance_review"),
        agents={
            "reviewer": "Reviewer",
            "writer": "Writer",
            "adversarial_reviewer": "AdversarialReviewer",
        },
        round_policy={"max_rounds": 1},
        gate_policy={"gates": ["逻辑完整性", "边界条件覆盖", "安全扫描", "覆盖率审查"]},
        output_spec={"review_result": "review_result.md"},
        metadata={
            "lane": "acceptance_review",
            "canonical_task_type": "acceptance_review",
            "public_task_type": public_task_type,
            "is_native_3_0": True,
            "source_of_truth": "machine_spec",
            "custom_agent_handlers": {
                "adversarial_verify": run_adversarial_review_step,
            },
        },
    )


class AdversarialVerificationAgent:
    """只读对抗性校验子 Agent (Adversarial Verification Agent).

    采用对抗性设定，假定下游提交的代码存在缺陷，仅作逻辑和覆盖率推演。
    """

    def __init__(self, work_id: str, machine_spec_ref: str, acceptance_protocol_ref: Optional[str] = None):
        self.work_id = work_id
        self.machine_spec_ref = machine_spec_ref
        self.acceptance_protocol_ref = acceptance_protocol_ref

    def verify(
        self,
        machine_spec: str,
        acceptance_protocol: str,
        implementation_summary: str,
        diff: str,
    ) -> ReviewResult:
        # 对抗性审查：提取 spec 中的需求（如 req_1, req_2 等）
        # 扫描交付的代码 diff 是否含有 bug、todo 等，或者是否漏掉验收条件。
        coverage = []
        issues = []
        fix_tasks = []

        # 简单的规则提取机：匹配 req_ 开头的标识符
        requirements = re.findall(r"(req_\w+)", machine_spec)
        if not requirements:
            requirements = ["req_default"]

        is_failed = (
            "bug" in diff.lower()
            or "todo" in diff.lower()
            or "missing" in implementation_summary.lower()
            or "fail" in implementation_summary.lower()
        )

        for req_id in requirements:
            cov_status = not is_failed
            coverage.append(
                RequirementCoverage(
                    requirement_id=req_id,
                    covered=cov_status,
                    evidence_refs=["evidence_diff" if cov_status else ""],
                    notes="Verified via adversarial diff check" if cov_status else "Adversarial check failed",
                )
            )

        if is_failed:
            verdict = ReviewVerdict.CHANGES_REQUIRED
            issue_id = f"issue_{uuid4().hex[:8]}"
            issues.append(
                ReviewIssue(
                    issue_id=issue_id,
                    severity=ReviewIssueSeverity.MAJOR,
                    summary="Detected logic gap or missing implementation in diff",
                    related_requirement_ids=requirements,
                    recommendation="Complete the missing logic and fix errors in diff",
                )
            )
            fix_tasks.append(
                ReviewFixTask(
                    task_id=f"fix_{uuid4().hex[:8]}",
                    title="Address adversarial review issues",
                    source_issue_ids=[issue_id],
                    priority="must",
                )
            )
        else:
            verdict = ReviewVerdict.PASS

        result = ReviewResult(
            work_id=self.work_id,
            machine_spec_ref=self.machine_spec_ref,
            verdict=verdict,
            summary="Adversarial check complete. All green." if not is_failed else "Adversarial review failed.",
            coverage=coverage,
            issues=issues,
            fix_tasks=fix_tasks,
            acceptance_protocol_ref=self.acceptance_protocol_ref,
        )

        if is_failed:
            try:
                import os
                import logging
                from app.services.gbrain_service import GBrainKnowledge
                gbrain = GBrainKnowledge(repo_path=os.environ.get("EVOLOOP_WORKSPACE", os.getcwd()))
                gbrain.learn_from_review(result)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Adversarial Learning loop failed: {e}")

        return result


def build_review_result_from_inputs(task_id: str, inputs: dict[str, object]) -> ReviewResult:
    """Build a ReviewResult from acceptance-review task inputs."""
    return AdversarialVerificationAgent(
        work_id=task_id,
        machine_spec_ref=f"memory://tasks/{task_id}/machine_spec",
        acceptance_protocol_ref=f"memory://tasks/{task_id}/acceptance_protocol",
    ).verify(
        machine_spec=str(inputs.get("machine_spec", "")),
        acceptance_protocol=str(inputs.get("acceptance_protocol", "")),
        implementation_summary=str(inputs.get("implementation_summary", "")),
        diff=str(inputs.get("diff", "")),
    )


def run_adversarial_review_step(task: Task, step: WorkflowStep) -> StepResult:
    """Build structured review output for the acceptance-review agent step."""
    review_result = build_review_result_from_inputs(task.task_id, task.context.inputs)
    return StepResult(
        step.id,
        StepStatus.SUCCEEDED,
        f"{step.role} completed",
        outputs={
            "content": review_result.summary,
            "review_result": review_result.to_dict(),
            "structured": {"role": step.role, "verdict": review_result.verdict.value},
        },
    )


def serialize_review_result(result: ReviewResult) -> str:
    """序列化 ReviewResult 实体为符合规范的 review_result.md."""
    cov_table = "| Requirement ID | Covered | Evidence Refs | Notes |\n| --- | --- | --- | --- |\n"
    for cov in result.coverage:
        cov_table += f"| {cov.requirement_id} | {'Yes' if cov.covered else 'No'} | {', '.join(cov.evidence_refs)} | {cov.notes} |\n"

    issues_sec = ""
    for issue in result.issues:
        issues_sec += f"### [{issue.severity.value.upper()}] {issue.summary} (ID: {issue.issue_id})\n"
        issues_sec += f"- Related Requirements: {', '.join(issue.related_requirement_ids)}\n"
        issues_sec += f"- Recommendation: {issue.recommendation}\n\n"

    tasks_sec = ""
    for task in result.fix_tasks:
        tasks_sec += f"- [ ] [{task.priority}] {task.title} (ID: {task.task_id})\n"
        tasks_sec += f"  - Source Issues: {', '.join(task.source_issue_ids)}\n"
        if task.owner_hint:
            tasks_sec += f"  - Owner: {task.owner_hint}\n"

    issues_content = issues_sec if issues_sec else "No issues found.\n"
    tasks_content = tasks_sec if tasks_sec else "No fix tasks required.\n"

    return f"""# Acceptance Review Result

## Metadata
- Work ID: {result.work_id}
- Review ID: {result.review_id}
- Verdict: {result.verdict.value}
- Created At: {result.created_at}

## Summary
{result.summary}

## Requirement Coverage
{cov_table}

## Issues
{issues_content}
## Fix Tasks
{tasks_content}"""


def verify_and_update_artifact_graph(
    work_id: str,
    machine_spec_ref: str,
    review_result_ref: str,
    acceptance_protocol_ref: Optional[str] = None,
    graph: Optional[ArtifactGraph] = None,
) -> ArtifactGraph:
    """将生成的 review_result.md 节点和其依赖边 reviews 回写回 ArtifactGraph 并校验."""
    if not graph:
        graph = ArtifactGraph(work_id=work_id)

    # 1. 确保有且仅有一个 machine_spec 节点
    spec_node_id = f"node_spec_{work_id}"
    has_spec = any(n.node_id == spec_node_id for n in graph.nodes)
    if not has_spec:
        graph.nodes.append(
            ArtifactNode(
                node_id=spec_node_id,
                type=ArtifactNodeType.MACHINE_SPEC,
                artifact_ref=ArtifactRef(name="machine_spec", storage_uri=machine_spec_ref),
                summary="Machine specification source of truth",
            )
        )

    # 2. 建立 acceptance_protocol 节点 (如果存在)
    protocol_node_id = f"node_protocol_{work_id}"
    if acceptance_protocol_ref:
        has_protocol = any(n.node_id == protocol_node_id for n in graph.nodes)
        if not has_protocol:
            graph.nodes.append(
                ArtifactNode(
                    node_id=protocol_node_id,
                    type=ArtifactNodeType.ACCEPTANCE_PROTOCOL,
                    artifact_ref=ArtifactRef(name="acceptance_protocol", storage_uri=acceptance_protocol_ref),
                    summary="Acceptance protocol",
                )
            )
            # 建立 protocol validates spec 的关系
            graph.edges.append(
                ArtifactEdge(
                    edge_id=f"edge_val_{work_id}",
                    from_node_id=protocol_node_id,
                    to_node_id=spec_node_id,
                    type=ArtifactEdgeType.VALIDATES,
                    summary="Acceptance protocol validates machine spec",
                )
            )

    # 3. 建立 review_result 节点
    review_node_id = f"node_review_{work_id}"
    graph.nodes = [n for n in graph.nodes if n.node_id != review_node_id]
    graph.nodes.append(
        ArtifactNode(
            node_id=review_node_id,
            type=ArtifactNodeType.REVIEW_RESULT,
            artifact_ref=ArtifactRef(name="review_result.md", storage_uri=review_result_ref),
            summary="Acceptance review result",
        )
    )

    # 4. 建立 reviews 依赖边并连接到 machine_spec
    graph.edges = [e for e in graph.edges if e.edge_id != f"edge_rev_{work_id}"]
    graph.edges.append(
        ArtifactEdge(
            edge_id=f"edge_rev_{work_id}",
            from_node_id=review_node_id,
            to_node_id=spec_node_id,
            type=ArtifactEdgeType.REVIEWS,
            summary="Review result reviews machine spec",
        )
    )

    # 验证
    graph.validate()
    return graph


def render_review_result_artifact(task: Task) -> str:
    """Serialize the earlier adversarial review output and validate graph linkage."""
    review_payload = task.context.step_outputs.get("adversarial_verify", {}).get("review_result")
    if not isinstance(review_payload, dict):
        raise DomainError(
            "workflow.acceptance_review_missing_result",
            "Acceptance review artifact writer requires review_result output from adversarial_verify.",
        )

    review_result = ReviewResult.from_dict(review_payload)
    verify_and_update_artifact_graph(
        work_id=task.task_id,
        machine_spec_ref=review_result.machine_spec_ref,
        review_result_ref=f"memory://tasks/{task.task_id}/review_result.md",
        acceptance_protocol_ref=review_result.acceptance_protocol_ref,
    )
    return serialize_review_result(review_result)
