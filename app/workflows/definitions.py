"""TaskDefinition registry for all product lines."""
from __future__ import annotations

from app.core.task import TaskDefinition
from app.workflows.manual import build_manual_definition
from app.workflows.prd import build_prd_definition


def build_task_registry() -> dict[str, TaskDefinition]:
    return {
        "manual": build_manual_definition(),
        "prd": build_prd_definition(),
    }
