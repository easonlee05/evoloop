"""Frozen 3.0 playbook, context, gate, and worker adapter contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.events import utc_now_iso


class DecisionGateStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class WorkerTargetType(str, Enum):
    WEB = "web"
    CLI = "cli"
    MCP = "mcp"
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"


@dataclass
class SourceInput:
    input_id: str
    kind: str
    summary: str
    source_ref: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceInput":
        return cls(
            input_id=data["input_id"],
            kind=data["kind"],
            summary=data.get("summary", ""),
            source_ref=data.get("source_ref"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class Requirement:
    requirement_id: str
    statement: str
    priority: str = "must"
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Requirement":
        return cls(
            requirement_id=data["requirement_id"],
            statement=data["statement"],
            priority=data.get("priority", "must"),
            rationale=data.get("rationale", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductConstraint:
    constraint_id: str
    statement: str
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductConstraint":
        return cls(
            constraint_id=data["constraint_id"],
            statement=data["statement"],
            category=data.get("category", "general"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductAssumption:
    assumption_id: str
    statement: str
    status: str = "open"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductAssumption":
        return cls(
            assumption_id=data["assumption_id"],
            statement=data["statement"],
            status=data.get("status", "open"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class KnowledgeRef:
    knowledge_id: str
    kind: str
    summary: str
    locator: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeRef":
        return cls(
            knowledge_id=data["knowledge_id"],
            kind=data["kind"],
            summary=data.get("summary", ""),
            locator=data.get("locator"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WorkerFeedback:
    feedback_id: str
    worker_id: str
    summary: str
    status: str = "info"
    related_artifact_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerFeedback":
        return cls(
            feedback_id=data["feedback_id"],
            worker_id=data["worker_id"],
            summary=data.get("summary", ""),
            status=data.get("status", "info"),
            related_artifact_ids=list(data.get("related_artifact_ids", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionOption:
    option_id: str
    label: str
    summary: str = ""
    consequences: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionOption":
        return cls(
            option_id=data["option_id"],
            label=data["label"],
            summary=data.get("summary", ""),
            consequences=list(data.get("consequences", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class GateResolution:
    selected_option_id: str
    rationale: str = ""
    decided_by: str = "user"
    decided_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateResolution":
        return cls(
            selected_option_id=data["selected_option_id"],
            rationale=data.get("rationale", ""),
            decided_by=data.get("decided_by", "user"),
            decided_at=data.get("decided_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionGate:
    """Decision Gate (Evoloop 3.0 Frozen Contract).

    Exposes questions that require human arbitration rather than letting AI make assumptions.
    """

    gate_id: str
    work_id: str
    question: str
    options: List[DecisionOption]
    impact_summary: str
    blocking: bool = True
    status: DecisionGateStatus = DecisionGateStatus.OPEN
    resolution: Optional[GateResolution] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["options"] = [item.to_dict() for item in self.options]
        if self.resolution is not None:
            data["resolution"] = self.resolution.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionGate":
        return cls(
            gate_id=data["gate_id"],
            work_id=data["work_id"],
            question=data["question"],
            options=[DecisionOption.from_dict(item) for item in data.get("options", [])],
            impact_summary=data.get("impact_summary", ""),
            blocking=bool(data.get("blocking", True)),
            status=DecisionGateStatus(data.get("status", DecisionGateStatus.OPEN.value)),
            resolution=GateResolution.from_dict(data["resolution"]) if data.get("resolution") else None,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductContext:
    """Product Context (Evoloop 3.0 Frozen Contract).

    Serves as the cross-run, cross-adapter single source of product requirements,
    constraints, assumptions, and human decisions.
    """

    objective: str
    source_inputs: List[SourceInput] = field(default_factory=list)
    requirements: List[Requirement] = field(default_factory=list)
    constraints: List[ProductConstraint] = field(default_factory=list)
    assumptions: List[ProductAssumption] = field(default_factory=list)
    user_decisions: List[DecisionGate] = field(default_factory=list)
    knowledge_refs: List[KnowledgeRef] = field(default_factory=list)
    worker_feedback: List[WorkerFeedback] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "source_inputs": [item.to_dict() for item in self.source_inputs],
            "requirements": [item.to_dict() for item in self.requirements],
            "constraints": [item.to_dict() for item in self.constraints],
            "assumptions": [item.to_dict() for item in self.assumptions],
            "user_decisions": [item.to_dict() for item in self.user_decisions],
            "knowledge_refs": [item.to_dict() for item in self.knowledge_refs],
            "worker_feedback": [item.to_dict() for item in self.worker_feedback],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductContext":
        return cls(
            objective=data.get("objective", ""),
            source_inputs=[SourceInput.from_dict(item) for item in data.get("source_inputs", [])],
            requirements=[Requirement.from_dict(item) for item in data.get("requirements", [])],
            constraints=[ProductConstraint.from_dict(item) for item in data.get("constraints", [])],
            assumptions=[ProductAssumption.from_dict(item) for item in data.get("assumptions", [])],
            user_decisions=[DecisionGate.from_dict(item) for item in data.get("user_decisions", [])],
            knowledge_refs=[KnowledgeRef.from_dict(item) for item in data.get("knowledge_refs", [])],
            worker_feedback=[WorkerFeedback.from_dict(item) for item in data.get("worker_feedback", [])],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class PlaybookStep:
    step_id: str
    title: str
    purpose: str
    allowed_tools: List[str] = field(default_factory=list)
    produces_artifact_types: List[str] = field(default_factory=list)
    next_step_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybookStep":
        return cls(
            step_id=data["step_id"],
            title=data.get("title", ""),
            purpose=data.get("purpose", ""),
            allowed_tools=list(data.get("allowed_tools", [])),
            produces_artifact_types=list(data.get("produces_artifact_types", [])),
            next_step_ids=list(data.get("next_step_ids", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class Playbook:
    """Playbook (Evoloop 3.0 Frozen Contract).

    Defines the work playbook of the digital product manager, specifying steps,
    allowed tools, and produced artifact types.
    """

    playbook_id: str
    version: str
    trigger_types: List[str]
    steps: List[PlaybookStep]
    decision_gate_ids: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    output_artifact_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "version": self.version,
            "trigger_types": list(self.trigger_types),
            "steps": [item.to_dict() for item in self.steps],
            "decision_gate_ids": list(self.decision_gate_ids),
            "allowed_tools": list(self.allowed_tools),
            "output_artifact_types": list(self.output_artifact_types),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playbook":
        return cls(
            playbook_id=data["playbook_id"],
            version=data["version"],
            trigger_types=list(data.get("trigger_types", [])),
            steps=[PlaybookStep.from_dict(item) for item in data.get("steps", [])],
            decision_gate_ids=list(data.get("decision_gate_ids", [])),
            allowed_tools=list(data.get("allowed_tools", [])),
            output_artifact_types=list(data.get("output_artifact_types", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WorkerAdapter:
    """Worker Adapter (Evoloop 3.0 Frozen Contract).

    Defines the interface and invocation policies to hand off tasks to downstream
    AI workers (e.g. Codex, Claude Code, Cursor).
    """

    adapter_id: str
    target_type: WorkerTargetType
    package_format: str
    invocation_policy: Dict[str, Any] = field(default_factory=dict)
    result_intake_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["target_type"] = self.target_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerAdapter":
        return cls(
            adapter_id=data["adapter_id"],
            target_type=WorkerTargetType(data["target_type"]),
            package_format=data["package_format"],
            invocation_policy=dict(data.get("invocation_policy", {})),
            result_intake_policy=dict(data.get("result_intake_policy", {})),
            metadata=dict(data.get("metadata", {})),
        )
