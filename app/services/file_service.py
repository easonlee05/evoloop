"""User-safe artifact and material file facade."""
from __future__ import annotations

from typing import Any


class FileService:
    def __init__(self, storage: Any):
        self.storage = storage

    def write_artifact(self, task_id: str, name: str, content: str, created_by: str = "Writer"):
        return self.storage.write_artifact(task_id=task_id, name=name, content=content, created_by=created_by)

    def read_artifact(self, artifact_id: str):
        return self.storage.read_artifact(artifact_id)

    def list_artifacts(self, task_id: str):
        return self.storage.list_artifacts(task_id)

    def backup_artifact(self, artifact_id: str):
        return self.storage.backup_artifact(artifact_id)
