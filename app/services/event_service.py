"""Event append and replay service."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.events import Event


class EventService:
    def __init__(self, storage: Any):
        self.storage = storage

    def emit(self, task_id: str, event_type: str, payload: Dict[str, Any] | None = None, role: Optional[str] = None, status: Optional[str] = None) -> Event:
        event = Event(task_id=task_id, type=event_type, payload=payload or {}, role=role, status=status)
        return self.storage.append_event(event)

    def replay(self, task_id: str) -> List[Event]:
        return self.storage.read_events(task_id)
