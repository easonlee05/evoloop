"""API DTOs for the refactored backend contract."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - allows py_compile without pydantic in minimal envs
    class BaseModel:  # type: ignore
        pass


class CreateTaskRequest(BaseModel):
    type: Optional[str] = None
    username: Optional[str] = None
    prompt: Optional[str] = None
    title: Optional[str] = None
    goal: Optional[str] = None
    feature: Optional[str] = None
    business_goal: Optional[str] = None
    module_name: Optional[str] = None
    instructions: Optional[str] = None
    constraints: List[str] = []
    preferences: List[str] = []
    material_ids: List[str] = []
    knowledge_scope: Optional[str] = None
    force_arbitration: bool = False
    model: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: str
    selected_option: Optional[str] = None
    quoted_selections: List[Dict[str, Any]] = []


class MaterialUploadResponse(BaseModel):
    material_id: str
    status: str
    summary: str
