"""Generic WorkflowEngine for TaskDefinition-driven task execution."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.context import UserDecision
from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import StepResult, StepStatus, Task, TaskStatus, WorkflowStep
from app.core.tools import ToolCall
from app.workflows.acceptance_review import render_review_result_artifact


class WorkflowEngine:
    def __init__(self, tool_service: Any, llm: Any, storage: Any):
        self.tool_service = tool_service
        self.llm = llm
        self.storage = storage

    def run(self, task: Task, start_step_id: Optional[str] = None, until_step_id: Optional[str] = None) -> Task:
        if task.status not in (TaskStatus.CREATED, TaskStatus.RUNNING):
            return task
            
        run_id = f"run_{uuid4().hex[:12]}"
        run_started_at = time.monotonic()
        task.status = TaskStatus.RUNNING
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.started", status=task.status.value, payload={"task_type": task.definition.type}))
        self.storage.append_event(Event(task_id=task.task_id, type="workflow.run.started", status=task.status.value, payload={"run_id": run_id, "task_type": task.definition.type, "start_step_id": start_step_id}))

        from concurrent.futures import ThreadPoolExecutor, as_completed

        start_index = self._start_index(task, start_step_id)
        steps_to_run = task.definition.workflow.steps[start_index:]
        
        # Group contiguous steps
        groups = []
        for step in steps_to_run:
            if not groups:
                groups.append([step])
            else:
                last_group = groups[-1]
                if step.parallel_group and last_group[-1].parallel_group == step.parallel_group:
                    last_group.append(step)
                else:
                    groups.append([step])

        for group in groups:
            if task.status == TaskStatus.CANCELLED:
                break
                
            if len(group) == 1:
                step = group[0]
                step_started_at = time.monotonic()
                self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.started", role=step.role, payload={"step_id": step.id, "step_type": step.type, "title": step.title, "run_id": run_id}))
                
                result = self._run_step(task, step, run_id=run_id)
                step_duration_ms = self._duration_ms(step_started_at)

                if result.status == StepStatus.SUCCEEDED:
                    task.context.step_outputs[step.id] = result.outputs
                    self.storage.save_context(task.context)
                    next_step_id = result.next_step_id or self._next_step_id(task, step.id)
                    task.status = TaskStatus.RUNNING
                    self.storage.save_checkpoint(task, step.id, next_step_id)
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.completed", role=step.role, status=result.status.value, payload={"step_id": step.id, "summary": result.summary, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    if until_step_id and step.id == until_step_id:
                        self._emit_run_finished(task, run_id, run_started_at, "partial")
                        return task
                    if result.next_step_id:
                        jump_index = task.definition.workflow.step_index(result.next_step_id)
                        return self.run(task, start_step_id=task.definition.workflow.steps[jump_index].id, until_step_id=until_step_id)
                    continue

                if result.status == StepStatus.NEEDS_ARBITRATION:
                    task.status = TaskStatus.WAITING_FOR_USER
                    task.waiting_step_id = result.next_step_id or step.id
                    task.resume_step_id = result.resume_step_id or step.pause_policy.get("resume_step_id") or self._next_step_id(task, step.id)
                    task.context.open_disputes.append(result.outputs.get("dispute_package", {}))
                    self.storage.save_context(task.context)
                    self.storage.save_checkpoint(task, task.waiting_step_id, task.resume_step_id)
                    self.storage.append_event(Event(task_id=task.task_id, type="arbitration.requested", role=step.role, status="needs_arbitration", payload={"step_id": task.waiting_step_id, "resume_step_id": task.resume_step_id, "dispute_package": result.outputs.get("dispute_package", {}), "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                if result.status == StepStatus.BLOCKED:
                    task.status = TaskStatus.BLOCKED
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="blocked", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                if result.status == StepStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    self.storage.append_event(Event(task_id=task.task_id, type="task.cancelled", status=task.status.value, payload={"step_id": step.id, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                task.status = TaskStatus.FAILED
                self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="failed", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms}))
                self.storage.append_event(Event(task_id=task.task_id, type="task.failed", status=task.status.value, payload={"step_id": step.id, "run_id": run_id}))
                self.storage.save_task(task)
                self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                return task
            else:
                # Parallel execution
                group_started_at = time.monotonic()
                for step in group:
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.started", role=step.role, payload={"step_id": step.id, "step_type": step.type, "title": step.title, "run_id": run_id, "parallel_group": step.parallel_group}))
                
                with ThreadPoolExecutor(max_workers=len(group)) as executor:
                    futures = {executor.submit(self._run_step, task, step, True, run_id): step for step in group}
                    results = {}
                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            results[step.id] = future.result()
                        except Exception as e:
                            from app.core.errors import DomainError
                            results[step.id] = StepResult(step.id, StepStatus.FAILED, error=DomainError("ParallelExecutionError", str(e)))
                
                for step in group:
                    result = results[step.id]
                    step_duration_ms = self._duration_ms(group_started_at)
                    if result.status == StepStatus.SUCCEEDED:
                        task.context.step_outputs[step.id] = result.outputs
                        self.storage.save_context(task.context)
                        next_step_id = result.next_step_id or self._next_step_id(task, step.id)
                        task.status = TaskStatus.RUNNING
                        self.storage.save_checkpoint(task, step.id, next_step_id)
                        self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.completed", role=step.role, status=result.status.value, payload={"step_id": step.id, "summary": result.summary, "run_id": run_id, "duration_ms": step_duration_ms, "parallel_group": step.parallel_group}))
                        self.storage.save_task(task)
                    else:
                        # On first failure in parallel group, abort
                        task.status = TaskStatus.FAILED
                        self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="failed", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms, "parallel_group": step.parallel_group}))
                        self.storage.append_event(Event(task_id=task.task_id, type="task.failed", status=task.status.value, payload={"step_id": step.id, "run_id": run_id}))
                        self.storage.save_task(task)
                        self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                        return task

        task.status = TaskStatus.COMPLETED
        self.storage.save_context(task.context)
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.completed", status=task.status.value, payload={"artifact_count": len(task.context.artifacts)}))
        self._emit_run_finished(task, run_id, run_started_at, task.status.value)
        return task

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, int((time.monotonic() - started_at) * 1000))

    def _emit_run_finished(self, task: Task, run_id: str, started_at: float, status: str) -> None:
        self.storage.append_event(Event(task_id=task.task_id, type="workflow.run.completed", status=status, payload={"run_id": run_id, "duration_ms": self._duration_ms(started_at), "task_status": task.status.value}))

    def apply_decision(
        self,
        task: Task,
        decision: str,
        selected_option: Optional[str] = None,
        quoted_selections: Optional[list[dict[str, Any]]] = None,
    ) -> Task:
        resume_step_id = task.resume_step_id or self._next_step_id(task, task.waiting_step_id or "")
        task.context.user_decisions.append(
            UserDecision(
                decision=decision,
                selected_option=selected_option,
                quoted_selections=list(quoted_selections or []),
                applies_to_step_id=task.waiting_step_id,
                resume_step_id=resume_step_id,
            )
        )
        task.context.open_disputes.clear()
        task.status = TaskStatus.RUNNING
        task.waiting_step_id = None
        task.resume_step_id = resume_step_id
        self.storage.save_context(task.context)
        self.storage.save_task(task)
        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="arbitration.applied",
                status="applied",
                payload={
                    "decision": decision,
                    "selected_option": selected_option,
                    "quoted_selections": list(quoted_selections or []),
                    "resume_step_id": resume_step_id,
                },
            )
        )
        return self.run(task, start_step_id=resume_step_id)

    def cancel(self, task: Task) -> Task:
        task.status = TaskStatus.CANCELLED
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.cancelled", status=task.status.value, payload={"reason": "user_cancelled"}))
        return task

    def _start_index(self, task: Task, start_step_id: Optional[str]) -> int:
        if start_step_id:
            return task.definition.workflow.step_index(start_step_id)
        checkpoint = self.storage.load_checkpoint(task.task_id)
        if checkpoint.get("next_step_id") and checkpoint.get("status") != TaskStatus.WAITING_FOR_USER.value:
            return task.definition.workflow.step_index(checkpoint["next_step_id"])
        return 0

    def _next_step_id(self, task: Task, step_id: str) -> Optional[str]:
        try:
            index = task.definition.workflow.step_index(step_id)
        except KeyError:
            return None
        if index + 1 >= len(task.definition.workflow.steps):
            return None
        return task.definition.workflow.steps[index + 1].id

    def _run_step(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        if step.type == "context":
            return self._run_context_step(task, step)
        if step.type == "agent":
            return self._run_agent_step(task, step, is_parallel, run_id=run_id)
        if step.type == "gate":
            return self._run_gate_step(task, step)
        if step.type == "arbitration":
            return self._run_arbitration_step(task, step)
        if step.type == "artifact":
            return self._run_artifact_step(task, step)
        if step.type == "diff":
            return StepResult(step.id, StepStatus.SUCCEEDED, "diff candidates prepared", outputs={"candidates": []})
        if step.type == "checkpoint":
            return StepResult(step.id, StepStatus.SUCCEEDED, "checkpoint saved", outputs={"checkpoint": step.id})
        return StepResult(step.id, StepStatus.FAILED, error=DomainError("workflow.unknown_step_type", f"Unknown step type: {step.type}"))

    def _run_context_step(self, task: Task, step: WorkflowStep) -> StepResult:
        if step.id == "retrieve_knowledge":
            query_parts = [task.context.title, task.context.goal, task.definition.type, task.context.inputs.get("feature"), task.context.inputs.get("business_goal")]
            query = " ".join(part.strip() for part in query_parts if isinstance(part, str) and part.strip())
            call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role="SYSTEM", tool_name="knowledge.retrieve", arguments={"query": query})
            result = self.tool_service.invoke(task.definition, task.context, call)
            if result.status != "succeeded":
                return StepResult(step.id, StepStatus.BLOCKED, error=result.error)
            task.context.knowledge_context = result.data
            preview = []
            for item in result.data.get("items", [])[:3]:
                if isinstance(item, dict):
                    preview.append({
                        "title": item.get("title", "未命名知识"),
                        "summary": item.get("summary", ""),
                    })
            task.context.degradation_state["knowledge"] = {
                "degraded": bool(result.data.get("degraded")),
                "error": result.data.get("error"),
                "items": len(result.data.get("items", [])),
                "preview": preview,
            }
            return StepResult(step.id, StepStatus.SUCCEEDED, "knowledge context loaded", outputs={"knowledge_context": result.data}, tool_calls=[call])
        if step.id == "ingest_materials":
            call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role="SYSTEM", tool_name="material.parse", arguments={})
            result = self.tool_service.invoke(task.definition, task.context, call)
            return StepResult(step.id, StepStatus.SUCCEEDED, "materials ingested", outputs=result.data, tool_calls=[call])
        self.storage.append_event(Event(task_id=task.task_id, type="context.loaded", status="loaded", payload={"degraded": bool(task.context.degradation_state), "title": task.context.title, "degradation_state": task.context.degradation_state}))
        return StepResult(step.id, StepStatus.SUCCEEDED, "context ready", outputs={"goal": task.context.goal})

    def _run_agent_step(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        custom_handler = task.definition.metadata.get("custom_agent_handlers", {}).get(step.id)
        if callable(custom_handler):
            result = custom_handler(task, step)
            if result.status == StepStatus.SUCCEEDED:
                content = str(result.outputs.get("content", result.summary))
                structured = result.outputs.get("structured", {"role": step.role})
                task.context.round_history.append(
                    {"step_id": step.id, "role": step.role, "content": content, "structured": structured}
                )
                self.storage.append_event(
                    Event(
                        task_id=task.task_id,
                        type="agent.message.completed",
                        role=step.role,
                        status="completed",
                        payload={"step_id": step.id, "summary": content[:160], "content": content},
                    )
                )
            return result

        full_content = ""
        structured = {"role": step.role, "title": task.context.title, "goal": task.context.goal}
        telemetry = self._llm_telemetry(task.task_id, step, run_id)
        
        llm_context = {
            **task.context.inputs,
            "title": task.context.title,
            "goal": task.context.goal,
            "round_history": [
                {"role": h["role"], "content": h["content"]}
                for h in task.context.round_history
            ]
        }
        
        prompt = step.title
        if step.id == "pm_first_draft" and task.context.round_count > 0:
            prompt = f"{step.title} (当前为第 {task.context.round_count} 轮迭代：请仅针对上一轮 Tech 和 QA 的审核意见，输出需要局部修改的 PRD 章节或增补内容，无需重写未受影响的完整文档。)"
        
        try:
            stream = self.llm.invoke_stream(step.role, prompt, llm_context, telemetry=telemetry)
        except TypeError:
            stream = self.llm.invoke_stream(step.role, prompt, llm_context)

        for chunk in stream:
            if isinstance(chunk, dict) and chunk.get("type") == "event":
                self.storage.append_event(Event(task_id=task.task_id, type=chunk.get("name"), payload=chunk))
                continue
            
            full_content += chunk
            if not is_parallel:
                self.storage.append_event(Event(task_id=task.task_id, type="agent.message.chunk", role=step.role, payload={"step_id": step.id, "chunk": chunk}))
            
        task.context.round_history.append({"step_id": step.id, "role": step.role, "content": full_content, "structured": structured})
        self.storage.append_event(Event(task_id=task.task_id, type="agent.message.completed", role=step.role, status="completed", payload={"step_id": step.id, "summary": full_content[:160], "content": full_content}))
        outputs = {"content": full_content, "structured": structured}
        if step.id == "writer_final_prd":
            outputs["artifact_name"] = "PRD.md"
            if "背景" in full_content and "业务目标" in full_content:
                outputs["artifact_content"] = full_content
            else:
                outputs["artifact_content"] = self._render_prd(task)
        elif step.id in {"writer_overview", "writer_scene_docs"}:
            outputs["artifact_name"] = "模块概览.md"
            if "操作路径" in full_content or len(full_content) > 100:
                outputs["artifact_content"] = full_content
            else:
                outputs["artifact_content"] = self._render_manual(task)
        return StepResult(step.id, StepStatus.SUCCEEDED, f"{step.role} completed", outputs=outputs)

    def _llm_telemetry(self, task_id: str, step: WorkflowStep, run_id: Optional[str]):
        def emit(event_type: str, payload: Dict[str, Any]) -> None:
            safe_payload = self._safe_llm_payload(payload)
            safe_payload.update({"step_id": step.id, "role": step.role})
            if run_id:
                safe_payload["run_id"] = run_id
            self.storage.append_event(Event(task_id=task_id, type=event_type, role=step.role, status=safe_payload.get("status"), payload=safe_payload))

        return emit

    @staticmethod
    def _safe_llm_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        denied = {"api_key", "authorization", "headers", "messages", "prompt", "system_prompt", "user_prompt", "content"}
        safe: Dict[str, Any] = {}
        for key, value in payload.items():
            normalized = key.lower()
            if normalized in denied or "token" in normalized or "secret" in normalized or "key" in normalized:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
        return safe

    def _run_gate_step(self, task: Task, step: WorkflowStep) -> StepResult:
        if step.id == "convergence_gate":
            if task.context.inputs.get("force_arbitration") is not None:
                consensus_reached = not task.context.inputs.get("force_arbitration")
            else:
                llm_context = {
                    **task.context.inputs,
                    "title": task.context.title,
                    "goal": task.context.goal,
                    "round_history": [
                        {"role": h["role"], "content": h["content"]}
                        for h in task.context.round_history
                    ]
                }
                gate_prompt = "请作为严格的 Reviewer，评估历史记录中近期 Tech 和 QA 对 PM 方案的二审反馈。如果他们对方案基本认可且没有要求重大重构或修改（允许有轻微建议），请只回复“PASS”；如果存在未解决的严重异议或明确要求 PM 重新修改，请只回复“FAIL”。必须只回复这两个词之一。"
                try:
                    result = self.llm.invoke("Reviewer", gate_prompt, llm_context)
                    normalized = (result.content or "").strip().upper()
                    consensus_reached = normalized == "PASS"
                except Exception:
                    consensus_reached = False
            
            if not consensus_reached and not task.context.user_decisions:
                max_rounds = task.definition.round_policy.get("max_rounds", 3)
                task.context.round_count += 1
                
                if task.context.round_count >= max_rounds:
                    return StepResult(
                        step.id,
                        StepStatus.NEEDS_ARBITRATION,
                        f"convergence requires human arbitration (max rounds {max_rounds} reached)",
                        outputs={"dispute_package": self._build_convergence_dispute_package(task, task.context.round_count)},
                        next_step_id="arbitration_business_tradeoff",
                        resume_step_id="pm_after_arbitration",
                    )
                else:
                    gate = {"step_id": step.id, "status": "fail", "round": task.context.round_count}
                    task.context.gate_results.append(gate)
                    return StepResult(
                        step.id,
                        StepStatus.SUCCEEDED,
                        f"convergence failed, looping back. Round {task.context.round_count}",
                        outputs={"gate": gate},
                        next_step_id="pm_first_draft"
                    )

        gate = {"step_id": step.id, "status": "pass", "checks": task.definition.gate_policy.get("gates", [])}
        task.context.gate_results.append(gate)
        return StepResult(step.id, StepStatus.SUCCEEDED, "gate passed", outputs={"gate": gate})

    def _run_arbitration_step(self, task: Task, step: WorkflowStep) -> StepResult:
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
        return StepResult(step.id, StepStatus.NEEDS_ARBITRATION, "waiting for user decision", outputs={"dispute_package": dispute_package}, resume_step_id=step.pause_policy.get("resume_step_id"))

    def _build_convergence_dispute_package(self, task: Task, round_count: int) -> Dict[str, Any]:
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

    def _run_artifact_step(self, task: Task, step: WorkflowStep) -> StepResult:
        if task.definition.metadata.get("is_native_3_0"):
            try:
                name, content = self._native_artifact_payload(task, step)
            except DomainError as error:
                return StepResult(step.id, StepStatus.FAILED, error=error)
        else:
            output = task.context.step_outputs.get("writer_final_prd" if task.definition.type == "prd" else "writer_scene_docs", {})
            if output.get("artifact_name") and output.get("artifact_content"):
                name, content = output["artifact_name"], output["artifact_content"]
            elif task.definition.type == "prd":
                name, content = "PRD.md", self._render_prd(task)
            else:
                name, content = "模块概览.md", self._render_manual(task)
        call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role=step.role, tool_name="artifact.write", arguments={"name": name, "content": content})
        result = self.tool_service.invoke(task.definition, task.context, call)
        if result.status != "succeeded":
            return StepResult(step.id, StepStatus.BLOCKED if result.status == "denied" else StepStatus.FAILED, error=result.error)
        for artifact in result.artifacts:
            if not any(existing.artifact_id == artifact.artifact_id for existing in task.context.artifacts):
                task.context.artifacts.append(artifact)
            self.storage.append_event(Event(task_id=task.task_id, type="artifact.created", role=step.role, status="created", payload={"artifact_id": artifact.artifact_id, "name": artifact.name, "version": artifact.version}))
        return StepResult(step.id, StepStatus.SUCCEEDED, "artifact written", outputs={"artifacts": [artifact.to_dict() for artifact in result.artifacts]}, tool_calls=[call])

    def _render_prd(self, task: Task) -> str:
        decisions = "\n".join(f"- {item.decision}" for item in task.context.user_decisions) or "- 暂无用户裁决"
        evidence = self._extract_prd_evidence(task)
        is_points_gateway = "积分" in task.context.title or "积分" in task.context.goal
        roles = evidence["roles"] or (["用户", "风控运营", "客服", "审计"] if is_points_gateway else ["用户", "业务运营", "客服", "管理员"])
        scenarios = evidence["scenarios"] or (["签到", "下单返积分", "退款", "邀请"] if is_points_gateway else ["创建请求", "处理流转", "状态通知", "结果追踪"])
        problems = evidence["problems"] or (["异常积分套利", "积分损失", "风险识别滞后"] if is_points_gateway else ["流程效率不足", "状态不透明", "人工处理成本高"])
        constraints = task.context.user_constraints or ["不重构积分系统", "在积分入账前完成风险处置", "保留人工审核与追溯能力"]
        primary_action = "在积分入账前完成风险识别、拦截、延迟入账或转人工审核" if is_points_gateway else f"围绕“{task.context.goal}”建立可执行的业务闭环"
        risk_action = "降低异常积分套利和营销活动资金损失" if is_points_gateway else "降低人工协作成本并提升处理效率"
        trace_action = "为风控运营、客服和审计提供可解释的处置记录" if is_points_gateway else "为业务运营、客服和管理员提供可追溯的过程记录"
        entry_requirement = "支持签到、下单返积分、活动抽奖和邀请奖励等积分来源接入统一校验" if is_points_gateway else "支持核心业务请求的创建、受理、流转、通知和关闭"
        identify_requirement = "按用户 ID、设备 ID、IP、活动 ID、订单 ID 和邀请关系聚合风险特征" if is_points_gateway else "按用户、业务对象、处理节点、优先级和状态聚合任务上下文"
        action_requirement = "支持放行、拦截、延迟入账、人工审核和命中原因回传" if is_points_gateway else "支持提交、分派、升级、驳回、完成和结果回传"
        rule_requirements = [
            "频次规则：识别短时间高频签到、批量请求和异常设备聚集。",
            "订单规则：识别小号下单返积分、退款后保留积分和异常订单链路。",
            "邀请规则：识别邀请链路作假、循环邀请和同设备多账号邀请。",
            "策略配置：支持按活动、渠道和用户分层配置阈值、灰度比例和白名单。",
        ] if is_points_gateway else [
            "流转规则：按业务类型、优先级和处理时限分派任务。",
            "升级规则：识别超时、重复提交和高优先级请求并自动升级。",
            "权限规则：按角色控制查看、处理、驳回和关闭权限。",
            "配置能力：支持按业务线、渠道和用户分层配置流程规则。",
        ]
        metrics = "风险命中率、拦截金额、误杀率、人工审核通过率、客诉率和接口耗时" if is_points_gateway else "处理时长、按时完成率、升级率、驳回率、用户满意度和通知到达率"
        problem_statement = self._problem_statement(task, problems, is_points_gateway)
        return f"""# {task.context.title} PRD

## 1. 背景与问题定义
{task.context.title} {problem_statement}当前主要问题包括：{self._join_cn(problems)}。

## 2. 业务目标与非目标
### 业务目标
- {primary_action}。
- {risk_action}。
- {trace_action}。

### 非目标
- 首期不重构积分账户、结算或营销活动系统。
- 首期不建设通用风控中台，只交付积分场景网关能力。
- 首期不自动封禁用户账号，账号处置由现有风控或人工流程完成。

## 3. 用户角色与使用场景
- 目标角色：{self._join_cn(roles)}。
- 覆盖场景：{self._join_cn(scenarios)}。
- 典型链路：请求进入系统后，系统校验用户、业务对象、来源渠道和上下文，输出处理结果并沉淀审计记录。

## 4. 功能需求
- 请求接入：{entry_requirement}。
- 识别处理：{identify_requirement}。
- 处置动作：{action_requirement}。
- 审核闭环：人工审核结果可回写，用于后续规则优化和客诉解释。
- 可追溯记录：每次风险判断必须记录请求摘要、命中规则、处置动作和操作者。

## 5. 风控策略与规则
{chr(10).join(f"- {item}" for item in rule_requirements)}

## 6. 数据与指标
- 核心指标：{metrics}。
- 数据埋点：记录来源场景、风险等级、规则编号、处置动作、审核结论和最终积分状态。
- 看板需求：按日、活动、渠道、规则和处置动作查看风险趋势。

## 7. 异常流程与降级
- 规则服务不可用时按配置降级为延迟入账或放行并标记待复核。
- 外部依赖超时时返回明确降级原因，不得重复发放积分。
- 发现规则误杀时支持批量回滚处置结果并生成审计记录。
- 约束条件：{self._join_cn(constraints)}。

## 8. 验收标准
- 所有接入场景均能返回风险等级、处置动作和可解释命中原因。
- 命中高风险请求时，积分不得直接入账。
- 人工审核、回滚和审计链路可追溯到单次请求。
- PRD 评审记录覆盖 PM、Tech、QA 和 Reviewer 的结论。

## 9. 用户裁决
{decisions}
"""

    def _extract_prd_evidence(self, task: Task) -> Dict[str, List[str]]:
        source = "\n".join(
            str(value)
            for value in [task.context.title, task.context.goal, task.context.inputs.get("prompt", "")]
            if value
        )
        candidates = {
            "problems": ["签到脚本", "小号下单返积分", "退款套利", "邀请作弊", "异常积分套利", "积分损失"],
            "roles": ["用户", "风控运营", "客服", "审计"],
            "scenarios": ["签到", "下单返积分", "活动抽奖", "邀请奖励", "退款"],
        }
        return {key: [item for item in values if item in source] for key, values in candidates.items()}

    @staticmethod
    def _join_cn(items: List[str]) -> str:
        return "、".join(items)

    @staticmethod
    def _problem_statement(task: Task, problems: List[str], is_points_gateway: bool) -> str:
        if is_points_gateway:
            return "面向电商积分链路，在积分入账前识别并处置作弊风险。"
        return f"围绕“{task.context.goal}”建立清晰、可追踪、可验收的产品能力。"

    def _render_manual(self, task: Task) -> str:
        return f"# {task.context.title} 操作手册\n\n## 模块目标\n{task.context.goal}\n\n## 操作路径\n- 按用户材料和平台知识补全。\n"

    def _native_artifact_payload(self, task: Task, step: WorkflowStep) -> tuple[str, str]:
        if len(step.output_keys) != 1:
            raise DomainError(
                "workflow.native_artifact_contract_invalid",
                f"Native artifact step {step.id} must declare exactly one output_key.",
            )
        artifact_key = step.output_keys[0]
        artifact_name = task.definition.output_spec.get(artifact_key)
        if not artifact_name:
            raise DomainError(
                "workflow.native_artifact_contract_missing_name",
                f"Native artifact key {artifact_key} is missing from output_spec for {task.definition.type}.",
            )
        renderers = {
            "machine_spec": self._render_machine_spec,
            "human_brief": self._render_human_brief,
            "agent_package": self._render_agent_package,
            "acceptance": self._render_acceptance,
            "review_checklist": self._render_review_checklist,
            "traceability": self._render_traceability,
            "review_result": render_review_result_artifact,
        }
        renderer = renderers.get(artifact_key)
        if not renderer:
            raise DomainError(
                "workflow.native_artifact_renderer_missing",
                f"No native renderer registered for artifact key {artifact_key}.",
            )
        return artifact_name, renderer(task)

    def _render_machine_spec(self, task: Task) -> str:
        business_intent = task.context.inputs.get("business_intent") or task.context.goal
        constraints = task.context.user_constraints or ["none"]
        return "\n".join(
            [
                f"work_id: {task.task_id}",
                f"title: {json.dumps(task.context.title, ensure_ascii=False)}",
                f"objective: {json.dumps(task.context.goal, ensure_ascii=False)}",
                f"business_intent: {json.dumps(business_intent, ensure_ascii=False)}",
                "requirements:",
                f"  - id: req_primary",
                f"    statement: {json.dumps(str(business_intent), ensure_ascii=False)}",
                "constraints:",
                *[f"  - {json.dumps(str(item), ensure_ascii=False)}" for item in constraints],
            ]
        ) + "\n"

    def _render_human_brief(self, task: Task) -> str:
        return (
            f"# Human Brief\n\n"
            f"## Title\n{task.context.title}\n\n"
            f"## Objective\n{task.context.goal}\n\n"
            f"## Business Intent\n{task.context.inputs.get('business_intent', task.context.goal)}\n"
        )

    def _render_agent_package(self, task: Task) -> str:
        return (
            f"# Agent Package For Codex\n\n"
            f"- Work ID: {task.task_id}\n"
            f"- Source of Truth: `machine_spec.yaml`\n"
            f"- Objective: {task.context.goal}\n"
            f"- Primary Requirement: {task.context.inputs.get('business_intent', task.context.goal)}\n"
        )

    def _render_acceptance(self, task: Task) -> str:
        return (
            f"# Acceptance Protocol\n\n"
            f"## Required Outcome\n{task.context.goal}\n\n"
            f"## Checks\n"
            f"- Machine spec can be traced to the stated business intent.\n"
            f"- Agent package stays aligned with the machine spec.\n"
            f"- Reviewer can validate the delivered work against this protocol.\n"
        )

    def _render_review_checklist(self, task: Task) -> str:
        return (
            f"# Review Checklist\n\n"
            f"- [ ] `machine_spec.yaml` reflects `{task.context.inputs.get('business_intent', task.context.goal)}`.\n"
            f"- [ ] `human_brief.md` is readable by stakeholders.\n"
            f"- [ ] `agent_package_codex.md` is executable by downstream workers.\n"
            f"- [ ] `acceptance.md` defines clear pass/fail checks.\n"
            f"- [ ] `traceability.json` anchors outputs back to `req_primary`.\n"
        )

    def _render_traceability(self, task: Task) -> str:
        payload = {
            "work_id": task.task_id,
            "source_of_truth": "machine_spec.yaml",
            "requirements": [
                {
                    "requirement_id": "req_primary",
                    "statement": task.context.inputs.get("business_intent", task.context.goal),
                    "artifacts": [
                        "machine_spec.yaml",
                        "human_brief.md",
                        "agent_package_codex.md",
                        "acceptance.md",
                        "review_checklist.md",
                    ],
                }
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
