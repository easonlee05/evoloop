"""Application service for task creation, execution, decisions and cancellation."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime

from app.core.context import TaskContext
from app.core.events import Event
from app.core.task import Task, TaskDefinition, TaskStatus


class TaskService:
    def __init__(self, registry: Dict[str, TaskDefinition], engine: Any, storage: Any):
        self.registry = registry
        self.engine = engine
        self.storage = storage
        self._running_tasks = set()

    def create_task(self, task_type: str, payload: Dict[str, Any]) -> Task:
        if task_type not in self.registry:
            raise ValueError(f"unknown task type: {task_type}")
        definition = self.registry[task_type]
        self._validate_required(definition, payload)
        task_id = f"task_{uuid4().hex[:12]}"
        title = payload.get("title") or payload.get("feature") or payload.get("module_name") or payload.get("business_domain") or task_type
        goal = payload.get("goal") or payload.get("business_goal") or payload.get("instructions") or title
        constraints = payload.get("constraints") or payload.get("user_constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        context = TaskContext(
            task_id=task_id,
            task_type=task_type,
            username=payload["username"],
            goal=goal,
            title=title,
            user_constraints=list(constraints),
            source_materials=[{"material_id": material_id} for material_id in payload.get("material_ids", [])],
            inputs=dict(payload),
        )
        task = Task(definition=definition, context=context, task_id=task_id, status=TaskStatus.CREATED)
        self.storage.save_context(context)
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task_id, type="task.created", status=task.status.value, payload={"task_type": task_type, "title": title}))
        return task

    def run_task(self, task_id: str, until_step_id: Optional[str] = None) -> Task:
        if task_id in self._running_tasks:
            return self.storage.load_task(task_id, self.registry)
        self._running_tasks.add(task_id)
        try:
            task = self.storage.load_task(task_id, self.registry)
            return self.engine.run(task, until_step_id=until_step_id)
        finally:
            self._running_tasks.discard(task_id)

    def apply_decision(
        self,
        task_id: str,
        decision: str,
        selected_option: Optional[str] = None,
        quoted_selections: Optional[list[dict[str, Any]]] = None,
    ) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.apply_decision(
            task,
            decision=decision,
            selected_option=selected_option,
            quoted_selections=quoted_selections,
        )

    def cancel_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.cancel(task)

    def delete_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = True
        task.deleted_at = datetime.now().isoformat()
        self.storage.save_task(task)
        return task

    def restore_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = False
        task.deleted_at = None
        self.storage.save_task(task)
        return task

    def permanent_delete_task(self, task_id: str) -> None:
        if hasattr(self.storage, "delete_task_directory"):
            self.storage.delete_task_directory(task_id)

    def get_task(self, task_id: str) -> Task:
        return self.storage.load_task(task_id, self.registry)

    def _validate_required(self, definition: TaskDefinition, payload: Dict[str, Any]) -> None:
        missing = [field for field in definition.input_schema.get("required", []) if not payload.get(field)]
        if missing:
            raise ValueError(f"missing required fields for {definition.type}: {', '.join(missing)}")
