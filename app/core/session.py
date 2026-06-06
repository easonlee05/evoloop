"""Evoloop 3.1 AgentSession domain contracts.

AgentSession is the bounded reasoning unit inside a single Playbook agent step.
It records observable turns and observations, not private chain-of-thought.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.errors import DomainError
from app.core.events import utc_now_iso


class AgentSessionStatus(str, Enum):
    """Lifecycle state for a bounded AgentSession."""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTurn:
    """One observable model turn inside an AgentSession."""

    iteration: int
    role: str
    prompt_summary: str
    response_summary: str = ""
    raw_content: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "role": self.role,
            "prompt_summary": self.prompt_summary,
            "response_summary": self.response_summary,
            "raw_content": self.raw_content,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentObservation:
    """A schema/tool/runtime observation recorded for auditability."""

    kind: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "data": dict(self.data),
            "created_at": self.created_at,
        }


@dataclass
class AgentSessionState:
    """Mutable runtime state for a single AgentSession."""

    status: AgentSessionStatus = AgentSessionStatus.CREATED
    iteration: int = 0
    turns: List[AgentTurn] = field(default_factory=list)
    observations: List[AgentObservation] = field(default_factory=list)
    last_error: Optional[DomainError] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "iteration": self.iteration,
            "turns": [turn.to_dict() for turn in self.turns],
            "observations": [observation.to_dict() for observation in self.observations],
            "last_error": self.last_error.to_dict() if self.last_error else None,
        }


@dataclass
class AgentSession:
    """Bounded reasoning session for one workflow agent step."""

    task_id: str
    step_id: str
    agent_role: str
    goal: str
    input_context: Dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 4
    session_id: str = field(default_factory=lambda: f"session_{uuid4().hex[:12]}")
    state: AgentSessionState = field(default_factory=AgentSessionState)
    created_at: str = field(default_factory=utc_now_iso)

    def record_turn(self, turn: AgentTurn) -> None:
        self.state.turns.append(turn)
        self.state.iteration = max(self.state.iteration, turn.iteration)

    def record_observation(self, observation: AgentObservation) -> None:
        self.state.observations.append(observation)

    def to_trace(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "agent_role": self.agent_role,
            "goal": self.goal,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at,
            "state": self.state.to_dict(),
        }


@dataclass
class AgentRunResult:
    """Result returned by AgentRuntime to workflow executors."""

    session: AgentSession
    status: AgentSessionStatus
    content: str = ""
    structured: Dict[str, Any] = field(default_factory=dict)
    error: Optional[DomainError] = None
    degraded: bool = False

    @classmethod
    def succeeded(cls, session: AgentSession, content: str, structured: Dict[str, Any]) -> "AgentRunResult":
        session.state.status = AgentSessionStatus.SUCCEEDED
        return cls(session=session, status=AgentSessionStatus.SUCCEEDED, content=content, structured=structured, degraded=False)

    @classmethod
    def blocked(
        cls,
        session: AgentSession,
        content: str,
        error: DomainError,
        structured: Optional[Dict[str, Any]] = None,
    ) -> "AgentRunResult":
        session.state.status = AgentSessionStatus.BLOCKED
        session.state.last_error = error
        data = dict(structured or {})
        data["degraded"] = True
        return cls(session=session, status=AgentSessionStatus.BLOCKED, content=content, structured=data, error=error, degraded=True)
