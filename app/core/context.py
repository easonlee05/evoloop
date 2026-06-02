"""TaskContext and decision models shared by all task definitions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.core.artifacts import Artifact


@dataclass
class UserDecision:
    decision: str
    selected_option: Optional[str] = None
    quoted_selections: List[Dict[str, Any]] = field(default_factory=list)
    applies_to_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserDecision":
        return cls(
            decision=data["decision"],
            selected_option=data.get("selected_option"),
            quoted_selections=list(data.get("quoted_selections", [])),
            applies_to_step_id=data.get("applies_to_step_id"),
            resume_step_id=data.get("resume_step_id"),
        )


@dataclass
class TaskContext:
    task_id: str
    task_type: str
    username: str
    goal: str
    title: str
    user_constraints: List[str] = field(default_factory=list)
    source_materials: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_context: Dict[str, Any] = field(default_factory=dict)
    format_spec: Optional[str] = None
    round_history: List[Dict[str, Any]] = field(default_factory=list)
    round_count: int = 0
    open_disputes: List[Dict[str, Any]] = field(default_factory=list)
    user_decisions: List[UserDecision] = field(default_factory=list)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    degradation_state: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    step_outputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["user_decisions"] = [decision.to_dict() for decision in self.user_decisions]
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            username=data["username"],
            goal=data.get("goal", ""),
            title=data.get("title", ""),
            user_constraints=list(data.get("user_constraints", [])),
            source_materials=list(data.get("source_materials", [])),
            knowledge_context=dict(data.get("knowledge_context", {})),
            format_spec=data.get("format_spec"),
            round_history=list(data.get("round_history", [])),
            round_count=data.get("round_count", 0),
            open_disputes=list(data.get("open_disputes", [])),
            user_decisions=[UserDecision.from_dict(item) for item in data.get("user_decisions", [])],
            gate_results=list(data.get("gate_results", [])),
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts", [])],
            degradation_state=dict(data.get("degradation_state", {})),
            inputs=dict(data.get("inputs", {})),
            step_outputs=dict(data.get("step_outputs", {})),
        )
