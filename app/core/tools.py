"""Tool registration, calls, results and task-level authorization policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.artifacts import Artifact
from app.core.errors import DomainError


@dataclass
class ToolSpec:
    name: str
    version: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effect: str
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    failure_semantics: str = "Return ToolResult.status='failed' with a structured DomainError."
    event_semantics: str = "write/external tools emit tool.call.* structured events."


@dataclass
class ToolCall:
    task_id: str
    step_id: str
    agent_role: str
    tool_name: str
    arguments: Dict[str, Any]
    id: str = field(default_factory=lambda: f"tool_{uuid4().hex[:12]}")
    status: str = "created"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    call_id: str
    status: str
    summary: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Artifact] = field(default_factory=list)
    error: Optional[DomainError] = None


@dataclass
class ToolPolicyRule:
    role: str
    step_id: str
    allowed_tools: List[str]
    denied_tools: List[str] = field(default_factory=list)
    max_calls_per_step: int = 20
    require_user_approval_for: List[str] = field(default_factory=list)


@dataclass
class ToolPolicy:
    task_type: str
    rules: List[ToolPolicyRule] = field(default_factory=list)

    def is_allowed(self, role: str, step_id: str, tool_name: str) -> bool:
        for rule in self.rules:
            role_matches = rule.role in {role, "*"}
            step_matches = rule.step_id in {step_id, "*"}
            if not (role_matches and step_matches):
                continue
            if tool_name in rule.denied_tools:
                return False
            if "*" in rule.allowed_tools or tool_name in rule.allowed_tools:
                return True
        return False
