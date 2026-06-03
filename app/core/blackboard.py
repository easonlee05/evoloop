"""Blackboard for shared working memory in 3.0 Playbook DAG."""
from __future__ import annotations

from typing import Any, Dict, List
from dataclasses import dataclass, field

@dataclass
class BlackboardContext:
    """A slice of the product context shared on the blackboard."""
    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner_node: str = "system"


class Blackboard:
    """Shared state mechanism across DAG nodes."""
    def __init__(self):
        self._store: Dict[str, BlackboardContext] = {}

    def write(self, key: str, value: Any, owner_node: str, **metadata) -> None:
        """Write a slice to the blackboard."""
        self._store[key] = BlackboardContext(key=key, value=value, metadata=metadata, owner_node=owner_node)

    def read(self, key: str) -> Any:
        """Read a slice from the blackboard."""
        ctx = self._store.get(key)
        return ctx.value if ctx else None

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.value for k, v in self._store.items()}
