"""Fake ports used by Phase 1 tests and local contract demos."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.artifacts import Artifact
from app.core.context import TaskContext
from app.core.events import Event, EventBus
from app.core.ports import LLMResult
from app.core.task import Task, TaskDefinition

class FakeLLM:
    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        if role == "Reviewer":
            return LLMResult(content="PASS", structured={"role": role})
        title = context.get("title") or context.get("feature") or context.get("module_name") or "未命名任务"
        goal = context.get("goal") or context.get("business_goal") or ""
        content = f"{role} response for {title}: {goal}"
        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal})

    def invoke_stream(self, role: str, prompt: str, context: Dict[str, Any]):
        title = context.get("title") or context.get("feature") or context.get("module_name") or "未命名任务"
        goal = context.get("goal") or context.get("business_goal") or ""
        content = f"{role} response for {title}: {goal}"
        
        # Simulate typing letter by letter
        for char in content:
            yield char

class FakeKnowledge:
    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        return {
            "query": query,
            "scope": scope or "default",
            "items": [
                {"title": "本地知识快照", "summary": f"与 {query} 相关的占位知识。"},
            ],
            "degraded": False,
        }

class FakeStorage:
    def __init__(self, root: Path, event_bus: Optional[EventBus] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    def _task_dir(self, task_id: str) -> Path:
        path = self.root / "tasks" / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifacts_dir(self) -> Path:
        path = self.root / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_task(self, task: Task) -> None:
        self._task_dir(task.task_id).joinpath("task.json").write_text(
            json.dumps(task.to_record(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def delete_task_directory(self, task_id: str) -> None:
        import shutil
        path = self._task_dir(task_id)
        if path.exists():
            shutil.rmtree(path)

    def load_task(self, task_id: str, registry: Dict[str, TaskDefinition]) -> Task:
        data = json.loads(self._task_dir(task_id).joinpath("task.json").read_text(encoding="utf-8"))
        context = self.load_context(task_id)
        return Task.from_record(registry[data["task_type"]], context, data)

    def list_tasks(self, registry: Dict[str, TaskDefinition]) -> List[Task]:
        tasks_dir = self.root / "tasks"
        if not tasks_dir.exists():
            return []
        tasks = []
        for path in sorted(tasks_dir.glob("task_*/task.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                tasks.append(self.load_task(path.parent.name, registry))
            except Exception:
                pass
        return tasks

    def save_context(self, context: TaskContext) -> None:
        self._task_dir(context.task_id).joinpath("context.json").write_text(
            json.dumps(context.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_context(self, task_id: str) -> TaskContext:
        data = json.loads(self._task_dir(task_id).joinpath("context.json").read_text(encoding="utf-8"))
        return TaskContext.from_dict(data)

    def append_event(self, event: Event) -> Event:
        if event.type != "agent.message.chunk":
            events = self.read_events(event.task_id)
            if not event.id:
                event.id = f"evt_{len(events) + 1:06d}"
            with self._task_dir(event.task_id).joinpath("events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        else:
            if not event.id:
                import time
                event.id = f"chunk_{int(time.time()*1000)}"
                
        if self.event_bus:
            self.event_bus.publish(event)
        return event

    def read_events(self, task_id: str) -> List[Event]:
        path = self._task_dir(task_id) / "events.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(Event.from_dict(json.loads(line)))
        return events

    def save_checkpoint(self, task: Task, last_completed_step_id: str, next_step_id: Optional[str]) -> None:
        self._task_dir(task.task_id).joinpath("checkpoint.json").write_text(
            json.dumps(
                {
                    "task_id": task.task_id,
                    "last_completed_step_id": last_completed_step_id,
                    "next_step_id": next_step_id,
                    "status": task.status.value,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_checkpoint(self, task_id: str) -> Dict[str, Any]:
        path = self._task_dir(task_id) / "checkpoint.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_artifact(self, task_id: str, name: str, content: str, created_by: str = "Writer") -> Artifact:
        for artifact in self.list_artifacts(task_id):
            if artifact.name == name:
                return artifact
        artifact_id = f"artifact_{task_id}_{len(self.list_artifacts(task_id)) + 1:03d}"
        artifact = Artifact(
            artifact_id=artifact_id,
            task_id=task_id,
            name=name,
            version=1,
            created_by=created_by,
            summary=f"Generated {name}",
            content=content,
        )
        self._artifacts_dir().joinpath(f"{artifact_id}.json").write_text(
            json.dumps(artifact.to_dict(include_content=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return artifact

    def update_artifact(self, artifact_id: str, content: str, updated_by: str = "user") -> Artifact:
        current = self.read_artifact(artifact_id)
        if (current.content or "").strip() == (content or "").strip():
            return current
        updated = Artifact(
            artifact_id=artifact_id,
            task_id=current.task_id,
            name=current.name,
            version=current.version + 1,
            content_type=current.content_type,
            created_by=updated_by,
            summary=f"Updated {current.name}",
            content=content,
        )
        self._artifacts_dir().joinpath(f"{artifact_id}.json").write_text(
            json.dumps(updated.to_dict(include_content=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated

    def list_artifacts(self, task_id: str) -> List[Artifact]:
        artifacts = []
        for path in sorted(self._artifacts_dir().glob("artifact_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("task_id") == task_id:
                artifacts.append(Artifact.from_dict(data))
        return artifacts

    def read_artifact(self, artifact_id: str) -> Artifact:
        path = self._artifacts_dir() / f"{artifact_id}.json"
        return Artifact.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def backup_artifact(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self.read_artifact(artifact_id)
        backup_id = f"backup_{artifact_id}_v{artifact.version}"
        backup_path = self._artifacts_dir() / f"{backup_id}.json"
        backup_path.write_text(json.dumps(artifact.to_dict(include_content=True), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"backup_id": backup_id}
