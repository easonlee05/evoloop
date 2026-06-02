"""Knowledge retrieval adapter placeholder for GBrain/local snapshots."""
from __future__ import annotations

from typing import Any, Dict, Optional


class KnowledgeService:
    def __init__(self, backend: Any):
        self.backend = backend

    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        return self.backend.retrieve(query=query, scope=scope)
