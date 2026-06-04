"""Frozen 3.0 review contracts for acceptance and coverage reporting."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.events import utc_now_iso
from app.core.persistence import FilePersistenceMixin


class ReviewVerdict(str, Enum):
    PASS = "pass"
    PASS_WITH_NOTES = "pass_with_notes"
    CHANGES_REQUIRED = "changes_required"
    BLOCKED = "blocked"


class ReviewIssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass
class RequirementCoverage:
    requirement_id: str
    covered: bool
    evidence_refs: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequirementCoverage":
        return cls(
            requirement_id=data["requirement_id"],
            covered=bool(data.get("covered", False)),
            evidence_refs=list(data.get("evidence_refs", [])),
            notes=data.get("notes", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewIssue:
    issue_id: str
    severity: ReviewIssueSeverity
    summary: str
    related_requirement_ids: List[str] = field(default_factory=list)
    related_artifact_ids: List[str] = field(default_factory=list)
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewIssue":
        return cls(
            issue_id=data["issue_id"],
            severity=ReviewIssueSeverity(data["severity"]),
            summary=data.get("summary", ""),
            related_requirement_ids=list(data.get("related_requirement_ids", [])),
            related_artifact_ids=list(data.get("related_artifact_ids", [])),
            recommendation=data.get("recommendation", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewFixTask:
    task_id: str
    title: str
    source_issue_ids: List[str] = field(default_factory=list)
    priority: str = "must"
    owner_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewFixTask":
        return cls(
            task_id=data["task_id"],
            title=data.get("title", ""),
            source_issue_ids=list(data.get("source_issue_ids", [])),
            priority=data.get("priority", "must"),
            owner_hint=data.get("owner_hint"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewResult(FilePersistenceMixin):
    """Review Result (Evoloop 3.0 Frozen Contract).

    Expresses acceptance review conclusions, including requirement coverage,
    issues, and fix tasks. It explicitly anchors to the machine_spec.
    """

    work_id: str
    machine_spec_ref: str
    verdict: ReviewVerdict
    summary: str
    coverage: List[RequirementCoverage] = field(default_factory=list)
    issues: List[ReviewIssue] = field(default_factory=list)
    fix_tasks: List[ReviewFixTask] = field(default_factory=list)
    acceptance_protocol_ref: Optional[str] = None
    review_id: str = field(default_factory=lambda: f"review_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "work_id": self.work_id,
            "machine_spec_ref": self.machine_spec_ref,
            "acceptance_protocol_ref": self.acceptance_protocol_ref,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "coverage": [item.to_dict() for item in self.coverage],
            "issues": [item.to_dict() for item in self.issues],
            "fix_tasks": [item.to_dict() for item in self.fix_tasks],
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewResult":
        return cls(
            review_id=data.get("review_id", f"review_{uuid4().hex[:12]}"),
            work_id=data["work_id"],
            machine_spec_ref=data["machine_spec_ref"],
            acceptance_protocol_ref=data.get("acceptance_protocol_ref"),
            verdict=ReviewVerdict(data["verdict"]),
            summary=data.get("summary", ""),
            coverage=[RequirementCoverage.from_dict(item) for item in data.get("coverage", [])],
            issues=[ReviewIssue.from_dict(item) for item in data.get("issues", [])],
            fix_tasks=[ReviewFixTask.from_dict(item) for item in data.get("fix_tasks", [])],
            created_at=data.get("created_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )

