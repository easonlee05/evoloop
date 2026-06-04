"""Generic WorkflowEngine for TaskDefinition-driven task execution."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import inspect
from uuid import uuid4

from app.core.context import UserDecision
from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import StepResult, StepStatus, Task, TaskStatus, WorkflowStep
from app.core.tools import ToolCall
from app.workflows.checkpoints import CheckpointManager
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.executors import DefaultStepExecutorRegistryFactory
from app.workflows.retry_policy import RetryPolicyRuntime
from app.workflows.runtime import WorkflowRuntimePlan
from app.workflows.state_store import WorkflowStateStore


class WorkflowEngine:
    def __init__(self, tool_service: Any, llm: Any, storage: Any, context_compiler: Optional[ContextCompilerService] = None):
        self.tool_service = tool_service
        self.llm = llm
        self.storage = storage
        self.context_compiler = context_compiler or ContextCompilerService()
        self.checkpoints = CheckpointManager(storage)
        self.state_store = WorkflowStateStore()
        self.retry_runtime = RetryPolicyRuntime()
        self.step_executors = DefaultStepExecutorRegistryFactory(
            tool_service=tool_service,
            llm=llm,
            storage=storage,
            context_compiler=self.context_compiler,
            agent_callback=self._run_agent_step,
            gate_callback=self._run_gate_step,
            arbitration_callback=self._run_arbitration_step,
        ).build()

    def run(self, task: Task, start_step_id: Optional[str] = None, until_step_id: Optional[str] = None) -> Task:
        if task.status not in (TaskStatus.CREATED, TaskStatus.RUNNING):
            return task
            
        run_id = f"run_{uuid4().hex[:12]}"
        run_started_at = time.monotonic()
        task.status = TaskStatus.RUNNING
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.started", status=task.status.value, payload={"task_type": task.definition.type}))
        self.storage.append_event(Event(task_id=task.task_id, type="workflow.run.started", status=task.status.value, payload={"run_id": run_id, "task_type": task.definition.type, "start_step_id": start_step_id}))
        self.state_store.record_run_started(task.task_id, run_id, start_step_id=start_step_id)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        plan = WorkflowRuntimePlan.from_workflow(task.definition.workflow)
        start_id = start_step_id or self._checkpoint_start_step_id(task, plan)
        groups = plan.batches_from(start_id)

        for batch in groups:
            group = batch.steps
            if task.status == TaskStatus.CANCELLED:
                break
                
            if len(group) == 1:
                step = group[0]
                step_started_at = time.monotonic()
                self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.started", role=step.role, payload={"step_id": step.id, "step_type": step.type, "title": step.title, "run_id": run_id}))
                
                result = self._run_step_with_retry(task, step, run_id=run_id)
                step_duration_ms = self._duration_ms(step_started_at)

                if result.status == StepStatus.SUCCEEDED:
                    task.context.step_outputs[step.id] = result.outputs
                    self.storage.save_context(task.context)
                    next_step_id = plan.resolve_success_route(step.id, result)
                    task.status = TaskStatus.RUNNING
                    checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=step.id, next_step_id=next_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                    self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
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
                    task.resume_step_id = result.resume_step_id or step.pause_policy.get("resume_step_id") or plan.next_step_id(step.id)
                    task.context.open_disputes.append(result.outputs.get("dispute_package", {}))
                    self.storage.save_context(task.context)
                    checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=task.waiting_step_id, next_step_id=task.resume_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                    self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
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
                    futures = {executor.submit(self._run_step_with_retry, task, step, True, run_id): step for step in group}
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
                        next_step_id = plan.resolve_success_route(step.id, result)
                        task.status = TaskStatus.RUNNING
                        checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=step.id, next_step_id=next_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                        self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
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
        self.state_store.record_run_finished(task.task_id, run_id, status=status)
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
        resume_step_id = self.checkpoints.resume_step_id(checkpoint)
        if resume_step_id:
            return task.definition.workflow.step_index(resume_step_id)
        return 0

    def _checkpoint_start_step_id(self, task: Task, plan: WorkflowRuntimePlan) -> Optional[str]:
        checkpoint = self.storage.load_checkpoint(task.task_id)
        resume_step_id = self.checkpoints.resume_step_id(checkpoint)
        if resume_step_id:
            plan.step_index(resume_step_id)
            return resume_step_id
        return None

    def _next_step_id(self, task: Task, step_id: str) -> Optional[str]:
        return WorkflowRuntimePlan.from_workflow(task.definition.workflow).next_step_id(step_id)

    def _run_step_with_retry(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        attempt = 1
        while True:
            attempt_started_at = time.monotonic()
            try:
                result = self._run_step(task, step, is_parallel=is_parallel, run_id=run_id)
            except Exception as exc:
                result = self._exception_step_result(step, exc)

            if result.status not in (StepStatus.FAILED, StepStatus.BLOCKED):
                return result

            error_code = result.error.code if result.error else result.status.value
            decision = self.retry_runtime.evaluate(
                step,
                attempt=attempt,
                elapsed_ms=self._duration_ms(attempt_started_at),
                error_code=error_code,
            )
            payload = self.retry_runtime.to_event_payload(
                step,
                decision,
                error_message=result.error.message if result.error else None,
            )
            if run_id:
                payload["run_id"] = run_id
            if decision.should_retry:
                self.storage.append_event(
                    Event(
                        task_id=task.task_id,
                        type="workflow.step.retry_scheduled",
                        role=step.role,
                        status=decision.decision.value,
                        payload=payload,
                    )
                )
                attempt = decision.next_attempt
                continue

            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="workflow.step.retry_exhausted",
                    role=step.role,
                    status=decision.decision.value,
                    payload=payload,
                )
            )
            return result

    @staticmethod
    def _exception_step_result(step: WorkflowStep, exc: Exception) -> StepResult:
        return StepResult(
            step.id,
            StepStatus.FAILED,
            error=DomainError(
                exc.__class__.__name__,
                "Step execution failed; raw exception message redacted from workflow retry state.",
            ),
        )

    def _run_step(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        return self.step_executors.run(task, step, run_id=run_id, is_parallel=is_parallel)

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
            handler_signature = inspect.signature(custom_handler)
            if "llm" in handler_signature.parameters:
                result = custom_handler(task, step, llm=self.llm)
            else:
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
                outputs["artifact_content"] = self.context_compiler.render_prd(task)
        elif step.id in {"writer_overview", "writer_scene_docs"}:
            outputs["artifact_name"] = "模块概览.md"
            if "操作路径" in full_content or len(full_content) > 100:
                outputs["artifact_content"] = full_content
            else:
                outputs["artifact_content"] = self.context_compiler.render_manual(task)
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
        try:
            name, content = self.context_compiler.artifact_payload(task, step)
        except DomainError as error:
            return StepResult(step.id, StepStatus.FAILED, error=error)

        call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role=step.role, tool_name="artifact.write", arguments={"name": name, "content": content})
        result = self.tool_service.invoke(task.definition, task.context, call)
        if result.status != "succeeded":
            return StepResult(step.id, StepStatus.BLOCKED if result.status == "denied" else StepStatus.FAILED, error=result.error)
        for artifact in result.artifacts:
            if not any(existing.artifact_id == artifact.artifact_id for existing in task.context.artifacts):
                task.context.artifacts.append(artifact)
            self.storage.append_event(Event(task_id=task.task_id, type="artifact.created", role=step.role, status="created", payload={"artifact_id": artifact.artifact_id, "name": artifact.name, "version": artifact.version}))
        return StepResult(step.id, StepStatus.SUCCEEDED, "artifact written", outputs={"artifacts": [artifact.to_dict() for artifact in result.artifacts]}, tool_calls=[call])

