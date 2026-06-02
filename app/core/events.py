"""Structured event model for API/SSE consumers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
import queue
from collections import defaultdict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    task_id: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    role: Optional[str] = None
    status: Optional[str] = None
    id: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            id=data.get("id", ""),
            task_id=data["task_id"],
            type=data["type"],
            role=data.get("role"),
            status=data.get("status"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at", utc_now_iso()),
        )

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[queue.Queue]] = defaultdict(list)
        
    def subscribe(self, task_id: str) -> queue.Queue:
        q = queue.Queue()
        self.subscribers[task_id].append(q)
        return q
        
    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        if task_id in self.subscribers and q in self.subscribers[task_id]:
            self.subscribers[task_id].remove(q)
            
    def publish(self, event: Event) -> None:
        for q in self.subscribers.get(event.task_id, []):
            q.put(event)
