"""Ports that isolate the kernel from model, storage and knowledge providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class LLMResult:
    content: str
    structured: Dict[str, Any] = field(default_factory=dict)


class LLMPort(Protocol):
    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        ...


class KnowledgePort(Protocol):
    def retrieve(self, query: str, scope: str | None = None) -> Dict[str, Any]:
        ...


class StoragePort(Protocol):
    root: Any

    def append_event(self, event: Any) -> Any:
        ...

    def save_context(self, context: Any) -> None:
        ...
