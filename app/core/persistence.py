"""File persistence mixin for Evoloop 3.0 contracts."""
from __future__ import annotations

import json
from typing import Any, Dict, Type, TypeVar
import yaml

from app.core.errors import DomainError

T = TypeVar("T", bound="FilePersistenceMixin")


class FilePersistenceMixin:
    """Mixin that provides unified JSON/YAML file persistence capabilities."""

    def save_to_file(self, file_path: str) -> None:
        """Save the contract instance to a JSON or YAML file based on file extension."""
        try:
            data = self.to_dict()
            if file_path.endswith((".yaml", ".yml")):
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise DomainError(
                code="persistence.save_failed",
                message=f"Failed to save to {file_path}: {str(e)}"
            ) from e

    @classmethod
    def load_from_file(cls: Type[T], file_path: str) -> T:
        """Load a contract instance from a JSON or YAML file based on file extension."""
        try:
            if file_path.endswith((".yaml", ".yml")):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception as e:
            raise DomainError(
                code="persistence.load_failed",
                message=f"Failed to load from {file_path}: {str(e)}"
            ) from e

        try:
            return cls.from_dict(data)
        except Exception as e:
            raise DomainError(
                code="persistence.load_failed",
                message=f"Failed to instantiate {cls.__name__} from data: {str(e)}"
            ) from e
