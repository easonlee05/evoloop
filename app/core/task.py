"""Task and Workflow domain models for the new backend kernel."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.events import Event
from app.core.tools import ToolCall, ToolPolicy


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class StepStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_ARBITRATION = "needs_arbitration"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    id: str
    type: str
    title: str
    role: str = "SYSTEM"
    input_keys: List[str] = field(default_factory=list)
    output_keys: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    pause_policy: Dict[str, Any] = field(default_factory=dict)
    parallel_group: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None


@dataclass
class WorkflowSpec:
    name: str
    version: str
    steps: List[WorkflowStep]

    def step_index(self, step_id: str) -> int:
        for index, step in enumerate(self.steps):
            if step.id == step_id:
                return index
        raise KeyError(f"unknown workflow step: {step_id}")


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    summary: str = ""
    outputs: Dict[str, Any] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    error: Optional[DomainError] = None
    next_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None


@dataclass
class TaskDefinition:
    type: str
    display_name: str
    input_schema: Dict[str, Any]
    workflow: WorkflowSpec
    tool_policy: ToolPolicy
    agents: Dict[str, Any] = field(default_factory=dict)
    round_policy: Dict[str, Any] = field(default_factory=dict)
    gate_policy: Dict[str, Any] = field(default_factory=dict)
    output_spec: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    definition: TaskDefinition
    context: TaskContext
    status: TaskStatus = TaskStatus.CREATED
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    waiting_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[str] = None

    def to_record(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.definition.type,
            "status": self.status.value,
            "waiting_step_id": self.waiting_step_id,
            "resume_step_id": self.resume_step_id,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
        }

    @classmethod
    def from_record(cls, definition: TaskDefinition, context: TaskContext, data: Dict[str, Any]) -> "Task":
        return cls(
            definition=definition,
            context=context,
            status=TaskStatus(data.get("status", TaskStatus.CREATED.value)),
            task_id=data["task_id"],
            waiting_step_id=data.get("waiting_step_id"),
            resume_step_id=data.get("resume_step_id"),
            is_deleted=data.get("is_deleted", False),
            deleted_at=data.get("deleted_at"),
        )
