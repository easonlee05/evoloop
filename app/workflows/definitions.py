"""TaskDefinition registry for all product lines."""
from __future__ import annotations

from app.core.task import TaskDefinition
from app.workflows.acceptance_review import build_acceptance_review_definition
from app.workflows.manual import build_manual_definition
from app.workflows.prd import build_prd_definition
from app.workflows.spec_to_agent import build_spec_to_agent_definition


def build_task_registry() -> dict[str, TaskDefinition]:
    legacy_manual = build_manual_definition(public_task_type="legacy_manual")
    legacy_prd = build_prd_definition(public_task_type="legacy_prd")
    spec_to_agent = build_spec_to_agent_definition()
    acceptance_review = build_acceptance_review_definition()
    return {
        # Keep the old keys as aliases so frozen callers do not break while the
        # bridge shifts external semantics toward legacy_* playbooks.
        "legacy_manual": legacy_manual,
        "manual": legacy_manual,
        "legacy_prd": legacy_prd,
        "prd": legacy_prd,
        "spec_to_agent": spec_to_agent,
        "acceptance_review": acceptance_review,
    }
