"""Step executor registry used to decouple workflow dispatch from engine state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Protocol
import inspect

from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import StepResult, StepStatus, Task, WorkflowStep
from app.core.tools import ToolCall
from app.workflows.context_compiler import ContextCompilerService


class StepExecutor(Protocol):
    """Protocol implemented by concrete workflow step executors."""

    step_type: str

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        ...


@dataclass
class StepExecutionRegistry:
    """Dispatches workflow steps to registered executors by `WorkflowStep.type`."""

    executors: Iterable[StepExecutor] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._executors: Dict[str, StepExecutor] = {}
        for executor in self.executors:
            self.register(executor)

    def register(self, executor: StepExecutor) -> None:
        step_type = getattr(executor, "step_type", "")
        if not step_type:
            raise DomainError("workflow.executor_missing_type", "Step executor must declare a non-empty step_type.")
        self._executors[step_type] = executor

    def get(self, step_type: str) -> Optional[StepExecutor]:
        return self._executors.get(step_type)

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        executor = self.get(step.type)
        if executor is None:
            return StepResult(
                step.id,
                StepStatus.FAILED,
                error=DomainError("workflow.unknown_step_type", f"Unknown step type: {step.type}"),
            )
        return executor.run(task, step, run_id=run_id, is_parallel=is_parallel)


@dataclass
class ContextStepExecutor:
    """Executor for context-loading steps that do not need custom engine hooks."""

    tool_service: Any = None
    storage: Any = None
    custom_handlers: Dict[str, Any] = field(default_factory=dict)
    step_type: str = "context"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        custom_handler = self.custom_handlers.get(step.id)
        if callable(custom_handler):
            return custom_handler(task, step)
        if step.id == "retrieve_knowledge" and self.tool_service is not None:
            query_parts = [
                task.context.title,
                task.context.goal,
                task.definition.type,
                task.context.inputs.get("feature"),
                task.context.inputs.get("business_goal"),
            ]
            query = " ".join(part.strip() for part in query_parts if isinstance(part, str) and part.strip())
            call = ToolCall(task.task_id, step.id, "SYSTEM", "knowledge.retrieve", {"query": query})
            result = self.tool_service.invoke(task.definition, task.context, call)
            if result.status != "succeeded":
                return StepResult(step.id, StepStatus.BLOCKED, error=result.error)
            task.context.knowledge_context = result.data
            preview = self._knowledge_preview(result.data)
            task.context.degradation_state["knowledge"] = {
                "degraded": bool(result.data.get("degraded")),
                "error": result.data.get("error"),
                "items": len(result.data.get("items", [])),
                "preview": preview,
            }
            return StepResult(step.id, StepStatus.SUCCEEDED, "knowledge context loaded", outputs={"knowledge_context": result.data}, tool_calls=[call])
        if step.id == "ingest_materials" and self.tool_service is not None:
            call = ToolCall(task.task_id, step.id, "SYSTEM", "material.parse", {})
            result = self.tool_service.invoke(task.definition, task.context, call)
            return StepResult(step.id, StepStatus.SUCCEEDED, "materials ingested", outputs=result.data, tool_calls=[call])
        if self.storage is not None:
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="context.loaded",
                    status="loaded",
                    payload={
                        "degraded": bool(task.context.degradation_state),
                        "title": task.context.title,
                        "degradation_state": task.context.degradation_state,
                    },
                )
            )
        return StepResult(step.id, StepStatus.SUCCEEDED, "context ready", outputs={"goal": task.context.goal})

    @staticmethod
    def _knowledge_preview(data: Dict[str, Any]) -> list[dict[str, str]]:
        preview: list[dict[str, str]] = []
        for item in data.get("items", [])[:3]:
            if isinstance(item, dict):
                preview.append({"title": item.get("title", "未命名知识"), "summary": item.get("summary", "")})
        return preview


@dataclass
class DiffStepExecutor:
    step_type: str = "diff"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        return StepResult(step.id, StepStatus.SUCCEEDED, "diff candidates prepared", outputs={"candidates": []})


@dataclass
class CheckpointStepExecutor:
    step_type: str = "checkpoint"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        return StepResult(step.id, StepStatus.SUCCEEDED, "checkpoint saved", outputs={"checkpoint": step.id})


@dataclass
class ArtifactStepExecutor:
    tool_service: Any
    context_compiler: ContextCompilerService
    storage: Any = None
    step_type: str = "artifact"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        try:
            name, content = self.context_compiler.artifact_payload(task, step)
        except DomainError as error:
            return StepResult(step.id, StepStatus.FAILED, error=error)
        call = ToolCall(task.task_id, step.id, step.role, "artifact.write", {"name": name, "content": content})
        result = self.tool_service.invoke(task.definition, task.context, call)
        if result.status != "succeeded":
            status = StepStatus.BLOCKED if result.status == "denied" else StepStatus.FAILED
            return StepResult(step.id, status, error=result.error)
        for artifact in result.artifacts:
            if not any(existing.artifact_id == artifact.artifact_id for existing in task.context.artifacts):
                task.context.artifacts.append(artifact)
            if self.storage is not None:
                self.storage.append_event(
                    Event(
                        task_id=task.task_id,
                        type="artifact.created",
                        role=step.role,
                        status="created",
                        payload={"artifact_id": artifact.artifact_id, "name": artifact.name, "version": artifact.version},
                    )
                )
        return StepResult(step.id, StepStatus.SUCCEEDED, "artifact written", outputs={"artifacts": [artifact.to_dict() for artifact in result.artifacts]}, tool_calls=[call])


@dataclass
class DelegatingStepExecutor:
    """Adapter for engine methods that still own complex legacy behavior."""

    step_type: str
    callback: Any
    custom_handlers: Dict[str, Any] = field(default_factory=dict)

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        custom_handler = self.custom_handlers.get(step.id)
        if callable(custom_handler):
            signature = inspect.signature(custom_handler)
            kwargs: Dict[str, Any] = {}
            if "run_id" in signature.parameters:
                kwargs["run_id"] = run_id
            if "is_parallel" in signature.parameters:
                kwargs["is_parallel"] = is_parallel
            if "llm" in signature.parameters and hasattr(self.callback, "__self__"):
                kwargs["llm"] = getattr(self.callback.__self__, "llm", None)
            return custom_handler(task, step, **kwargs)
        signature = inspect.signature(self.callback)
        kwargs: Dict[str, Any] = {}
        if "run_id" in signature.parameters:
            kwargs["run_id"] = run_id
        if "is_parallel" in signature.parameters:
            kwargs["is_parallel"] = is_parallel
        return self.callback(task, step, **kwargs)


@dataclass
class DefaultStepExecutorRegistryFactory:
    """Builds the core executor registry for a workflow engine instance."""

    tool_service: Any
    llm: Any
    storage: Any
    context_compiler: ContextCompilerService
    agent_callback: Any = None
    gate_callback: Any = None
    arbitration_callback: Any = None
    context_handlers: Dict[str, Any] = field(default_factory=dict)
    agent_handlers: Dict[str, Any] = field(default_factory=dict)
    gate_handlers: Dict[str, Any] = field(default_factory=dict)
    arbitration_handlers: Dict[str, Any] = field(default_factory=dict)

    def build(self) -> StepExecutionRegistry:
        executors: list[StepExecutor] = [
            ContextStepExecutor(
                tool_service=self.tool_service,
                storage=self.storage,
                custom_handlers=self.context_handlers,
            ),
            ArtifactStepExecutor(tool_service=self.tool_service, context_compiler=self.context_compiler, storage=self.storage),
            DiffStepExecutor(),
            CheckpointStepExecutor(),
        ]
        executors.append(
            DelegatingStepExecutor(
                "agent",
                self.agent_callback or self._missing_delegate("agent"),
                custom_handlers=self.agent_handlers,
            )
        )
        executors.append(
            DelegatingStepExecutor(
                "gate",
                self.gate_callback or self._missing_delegate("gate"),
                custom_handlers=self.gate_handlers,
            )
        )
        executors.append(
            DelegatingStepExecutor(
                "arbitration",
                self.arbitration_callback or self._missing_delegate("arbitration"),
                custom_handlers=self.arbitration_handlers,
            )
        )
        return StepExecutionRegistry(executors)

    @staticmethod
    def _missing_delegate(step_type: str):
        def run(task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
            return StepResult(step.id, StepStatus.FAILED, error=DomainError("workflow.executor_not_bound", f"No delegate bound for {step_type} step."))
        return run
