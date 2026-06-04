"""Workflow checkpoint helpers with legacy storage compatibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from app.core.task import Task, TaskStatus


@dataclass
class CheckpointManager:
    """Builds transaction-style checkpoint payloads without requiring new storage."""

    storage: Any

    def resume_step_id(self, checkpoint: Dict[str, Any]) -> Optional[str]:
        if checkpoint.get("status") == TaskStatus.WAITING_FOR_USER.value:
            return None
        next_step_id = checkpoint.get("next_step_id")
        return str(next_step_id) if next_step_id else None

    def build_payload(
        self,
        *,
        task_id: str,
        run_id: str,
        last_completed_step_id: str,
        next_step_id: Optional[str],
        status: str,
        attempt: int = 1,
        completed_step_ids: Iterable[str] = (),
    ) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "run_id": run_id,
            "attempt": attempt,
            "last_completed_step_id": last_completed_step_id,
            "next_step_id": next_step_id,
            "status": status,
            "completed_step_ids": list(completed_step_ids),
        }

    def save_success_checkpoint(
        self,
        task: Task,
        *,
        run_id: str,
        last_completed_step_id: str,
        next_step_id: Optional[str],
        completed_step_ids: Iterable[str] = (),
        attempt: int = 1,
    ) -> Dict[str, Any]:
        payload = self.build_payload(
            task_id=task.task_id,
            run_id=run_id,
            last_completed_step_id=last_completed_step_id,
            next_step_id=next_step_id,
            status=task.status.value,
            attempt=attempt,
            completed_step_ids=completed_step_ids,
        )
        if self.storage is not None:
            save_transaction = getattr(self.storage, "save_transaction_checkpoint", None)
            if callable(save_transaction):
                save_transaction(task, payload)
            else:
                self.storage.save_checkpoint(task, last_completed_step_id, next_step_id)
        return payload


@dataclass
class CheckpointReplay:
    """Reconstructed checkpoint state from workflow events."""

    task_id: str
    completed_step_ids: list[str]
    attempts_by_step: Dict[str, int]
    failed_step_id: Optional[str] = None
    last_run_id: Optional[str] = None

    @classmethod
    def from_events(cls, task_id: str, events: Iterable[Any]) -> "CheckpointReplay":
        completed: list[str] = []
        attempts: Dict[str, int] = {}
        failed_step_id: Optional[str] = None
        last_run_id: Optional[str] = None
        for event in events:
            event_type, payload = cls._event_parts(event)
            step_id = payload.get("step_id")
            if not step_id:
                continue
            step_id = str(step_id)
            if payload.get("run_id"):
                last_run_id = str(payload["run_id"])
            if event_type == "workflow.step.started":
                attempts[step_id] = attempts.get(step_id, 0) + 1
            elif event_type == "workflow.step.completed":
                if attempts.get(step_id, 0) == 0:
                    attempts[step_id] = 1
                if step_id not in completed:
                    completed.append(step_id)
                if failed_step_id == step_id:
                    failed_step_id = None
            elif event_type == "workflow.step.failed":
                if attempts.get(step_id, 0) == 0:
                    attempts[step_id] = 1
                failed_step_id = step_id
        return cls(
            task_id=task_id,
            completed_step_ids=completed,
            attempts_by_step=attempts,
            failed_step_id=failed_step_id,
            last_run_id=last_run_id,
        )

    @staticmethod
    def _event_parts(event: Any) -> tuple[str, Dict[str, Any]]:
        if isinstance(event, dict):
            return str(event.get("type", "")), dict(event.get("payload", {}))
        return str(getattr(event, "type", "")), dict(getattr(event, "payload", {}) or {})

    def next_attempt_for(self, step_id: str) -> int:
        return self.attempts_by_step.get(step_id, 1) + 1

    def to_checkpoint_payload(self, next_step_id: Optional[str], status: str = "running") -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "last_completed_step_id": self.completed_step_ids[-1] if self.completed_step_ids else None,
            "next_step_id": next_step_id,
            "status": status,
            "completed_step_ids": list(self.completed_step_ids),
            "attempts_by_step": dict(self.attempts_by_step),
            "failed_step_id": self.failed_step_id,
            "last_run_id": self.last_run_id,
        }
