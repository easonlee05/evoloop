"""DAG-ready runtime planning primitives for TaskDefinition workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.errors import DomainError
from app.core.task import StepResult, WorkflowSpec, WorkflowStep


@dataclass(frozen=True)
class WorkflowExecutionBatch:
    """A contiguous executable batch.

    Single-step batches preserve legacy linear behavior. Multi-step batches represent
    the existing contiguous `parallel_group` contract and are ready to become DAG
    frontiers later.
    """

    steps: List[WorkflowStep]
    parallel_group: Optional[str] = None

    @property
    def is_parallel(self) -> bool:
        return len(self.steps) > 1


@dataclass(frozen=True)
class WorkflowRuntimePlan:
    """Validated execution plan derived from a `WorkflowSpec`."""

    workflow: WorkflowSpec
    step_by_id: Dict[str, WorkflowStep]
    order: List[str]

    @classmethod
    def from_workflow(cls, workflow: WorkflowSpec) -> "WorkflowRuntimePlan":
        step_by_id: Dict[str, WorkflowStep] = {}
        order: List[str] = []
        for step in workflow.steps:
            if step.id in step_by_id:
                raise DomainError(
                    "workflow.duplicate_step_id",
                    f"Workflow step id '{step.id}' appears more than once.",
                )
            step_by_id[step.id] = step
            order.append(step.id)

        plan = cls(workflow=workflow, step_by_id=step_by_id, order=order)
        plan._validate_routes()
        return plan

    def _validate_routes(self) -> None:
        for step in self.workflow.steps:
            for route_name, target in (("on_success", step.on_success), ("on_failure", step.on_failure)):
                if target and target not in self.step_by_id:
                    raise DomainError(
                        "workflow.dangling_route",
                        f"Step '{step.id}' has {route_name} route to unknown step '{target}'.",
                        details={"step_id": step.id, "route": route_name, "target": target},
                    )

    def step_index(self, step_id: str) -> int:
        if step_id not in self.step_by_id:
            raise KeyError(f"unknown workflow step: {step_id}")
        return self.order.index(step_id)

    def next_step_id(self, step_id: str) -> Optional[str]:
        index = self.step_index(step_id)
        if index + 1 >= len(self.order):
            return None
        return self.order[index + 1]

    def batches_from(self, start_step_id: Optional[str] = None) -> List[WorkflowExecutionBatch]:
        start_index = self.step_index(start_step_id) if start_step_id else 0
        groups: List[WorkflowExecutionBatch] = []
        current: List[WorkflowStep] = []
        current_group: Optional[str] = None

        for step in self.workflow.steps[start_index:]:
            if current and step.parallel_group and step.parallel_group == current_group:
                current.append(step)
                continue
            if current:
                groups.append(WorkflowExecutionBatch(steps=current, parallel_group=current_group))
            current = [step]
            current_group = step.parallel_group

        if current:
            groups.append(WorkflowExecutionBatch(steps=current, parallel_group=current_group))
        return groups

    def resolve_success_route(self, step_id: str, result: StepResult) -> Optional[str]:
        step = self.step_by_id[step_id]
        return result.next_step_id or step.on_success or self.next_step_id(step_id)

    def resolve_failure_route(self, step_id: str, result: StepResult) -> Optional[str]:
        step = self.step_by_id[step_id]
        return result.next_step_id or step.on_failure
