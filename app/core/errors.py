"""Domain errors shared by the refactored backend kernel."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class DomainError:
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "DomainError | None":
        if not data:
            return None
        return cls(
            code=data.get("code", "unknown"),
            message=data.get("message", ""),
            details=data.get("details"),
        )


class BackendDomainException(Exception):
    def __init__(self, error: DomainError):
        super().__init__(error.message)
        self.error = error
