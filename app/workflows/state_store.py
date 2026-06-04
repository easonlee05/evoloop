"""Workflow run/checkpoint history store and rollback planning helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class WorkflowRollbackPlan:
    task_id: str
    failed_step_id: str
    rollback_to_step_id: Optional[str]
    resume_step_id: Optional[str]
    discarded_step_ids: List[str]
    checkpoint: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowStateStore:
    """In-memory state ledger that mirrors event-sourced workflow state."""

    runs_by_task: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    checkpoints_by_task: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def record_run_started(self, task_id: str, run_id: str, *, start_step_id: Optional[str] = None) -> Dict[str, Any]:
        entry = {"event": "run.started", "task_id": task_id, "run_id": run_id, "start_step_id": start_step_id}
        self.runs_by_task.setdefault(task_id, []).append(entry)
        return entry

    def record_run_finished(self, task_id: str, run_id: str, *, status: str) -> Dict[str, Any]:
        entry = {"event": "run.finished", "task_id": task_id, "run_id": run_id, "status": status}
        self.runs_by_task.setdefault(task_id, []).append(entry)
        return entry

    def record_checkpoint(self, task_id: str, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        entry = dict(checkpoint)
        entry.setdefault("task_id", task_id)
        self.checkpoints_by_task.setdefault(task_id, []).append(entry)
        return entry

    def run_history(self, task_id: str) -> List[Dict[str, Any]]:
        return list(self.runs_by_task.get(task_id, []))

    def checkpoint_history(self, task_id: str) -> List[Dict[str, Any]]:
        return list(self.checkpoints_by_task.get(task_id, []))

    def latest_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        history = self.checkpoint_history(task_id)
        return history[-1] if history else None

    @classmethod
    def from_events(cls, task_id: str, events: Iterable[Any]) -> "WorkflowStateStore":
        store = cls()
        for event in events:
            event_type, payload = cls._event_parts(event)
            if event_type == "workflow.run.started":
                store.record_run_started(task_id, str(payload.get("run_id", "")), start_step_id=payload.get("start_step_id"))
            elif event_type == "workflow.run.completed":
                store.record_run_finished(task_id, str(payload.get("run_id", "")), status=str(payload.get("task_status") or payload.get("status") or "completed"))
            elif event_type == "workflow.step.completed":
                step_id = payload.get("step_id")
                if step_id:
                    store.record_checkpoint(
                        task_id,
                        {
                            "run_id": payload.get("run_id"),
                            "last_completed_step_id": step_id,
                            "next_step_id": payload.get("next_step_id"),
                            "status": "running",
                        },
                    )
        return store

    @staticmethod
    def _event_parts(event: Any) -> tuple[str, Dict[str, Any]]:
        if isinstance(event, dict):
            return str(event.get("type", "")), dict(event.get("payload", {}))
        return str(getattr(event, "type", "")), dict(getattr(event, "payload", {}) or {})


@dataclass
class WorkflowRollbackPlanner:
    state_store: WorkflowStateStore

    def plan_rollback(self, task_id: str, *, failed_step_id: str) -> WorkflowRollbackPlan:
        history = self.state_store.checkpoint_history(task_id)
        checkpoint = history[-1] if history else None
        rollback_to = checkpoint.get("last_completed_step_id") if checkpoint else None
        resume = checkpoint.get("next_step_id") if checkpoint else failed_step_id
        return WorkflowRollbackPlan(
            task_id=task_id,
            failed_step_id=failed_step_id,
            rollback_to_step_id=rollback_to,
            resume_step_id=resume,
            discarded_step_ids=[failed_step_id],
            checkpoint=checkpoint,
        )
