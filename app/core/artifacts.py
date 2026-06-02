"""Artifact domain objects and storage-facing metadata."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class Artifact:
    artifact_id: str
    task_id: str
    name: str
    version: int
    content_type: str = "text/markdown"
    created_by: str = "system"
    summary: str = ""
    content: Optional[str] = None

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        if not include_content:
            data.pop("content", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        return cls(
            artifact_id=data["artifact_id"],
            task_id=data["task_id"],
            name=data["name"],
            version=int(data.get("version", 1)),
            content_type=data.get("content_type", "text/markdown"),
            created_by=data.get("created_by", "system"),
            summary=data.get("summary", ""),
            content=data.get("content"),
        )
