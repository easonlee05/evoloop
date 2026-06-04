"""Frozen 3.0 work contracts for lane-safe integration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.events import utc_now_iso
from app.core.persistence import FilePersistenceMixin


class WorkType(str, Enum):
    SPEC_TO_AGENT = "spec_to_agent"
    ACCEPTANCE_REVIEW = "acceptance_review"
    CHANGE_IMPACT = "change_impact"
    FEEDBACK_INTAKE = "feedback_intake"
    LEGACY_PRD = "legacy_prd"
    LEGACY_MANUAL = "legacy_manual"


class WorkStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_DECISION = "waiting_for_decision"
    WAITING_FOR_WORKER = "waiting_for_worker"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class WorkItem(FilePersistenceMixin):
    """Minimal 3.0 work unit boundary (Evoloop 3.0 Frozen Contract).

    This object represents the unified work identity. It intentionally carries
    references to context and artifact graph rather than embedding runtime or
    workflow-engine execution details.
    """

    work_type: WorkType
    playbook_id: str
    title: str
    objective: str
    workspace_id: str
    product_context_ref: str
    artifact_graph_ref: str
    status: WorkStatus = WorkStatus.CREATED
    work_id: str = field(default_factory=lambda: f"work_{uuid4().hex[:12]}")
    current_decision_gate_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["work_type"] = self.work_type.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItem":
        return cls(
            work_id=data.get("work_id", f"work_{uuid4().hex[:12]}"),
            work_type=WorkType(data["work_type"]),
            playbook_id=data["playbook_id"],
            title=data.get("title", ""),
            objective=data.get("objective", ""),
            workspace_id=data.get("workspace_id", ""),
            product_context_ref=data["product_context_ref"],
            artifact_graph_ref=data["artifact_graph_ref"],
            status=WorkStatus(data.get("status", WorkStatus.CREATED.value)),
            current_decision_gate_id=data.get("current_decision_gate_id"),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


