"""DAG runtime primitives for native Evoloop playbooks.

This module is intentionally independent from LLM/tool execution. It converts the
existing `WorkflowSpec` contract into dependency-aware nodes so the legacy engine
can evolve toward a real `PlaybookDAGRuntime` without another contract rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from app.core.errors import DomainError
from app.core.task import WorkflowSpec, WorkflowStep


@dataclass(frozen=True)
class DAGRuntimeNode:
    """A workflow step plus explicit dependency and routing metadata."""

    step: WorkflowStep
    dependencies: List[str] = field(default_factory=list)

    @property
    def node_id(self) -> str:
        return self.step.id

    @property
    def step_type(self) -> str:
        return self.step.type


@dataclass
class PlaybookDAGRuntime:
    """Dependency-frontier scheduler for WorkflowSpec-backed playbooks."""

    nodes: Dict[str, DAGRuntimeNode]
    order: List[str]

    @classmethod
    def from_workflow(cls, workflow: WorkflowSpec) -> "PlaybookDAGRuntime":
        nodes: Dict[str, DAGRuntimeNode] = {}
        order: List[str] = []
        for index, step in enumerate(workflow.steps):
            if step.id in nodes:
                raise DomainError("workflow.duplicate_step_id", f"Workflow step id '{step.id}' appears more than once.")
            dependencies = cls._dependencies_for_step(step, workflow.steps, index)
            nodes[step.id] = DAGRuntimeNode(step=step, dependencies=dependencies)
            order.append(step.id)
        runtime = cls(nodes=nodes, order=order)
        runtime.validate()
        return runtime

    @staticmethod
    def _dependencies_for_step(step: WorkflowStep, steps: List[WorkflowStep], index: int) -> List[str]:
        explicit = [item for item in step.input_keys if item in {candidate.id for candidate in steps}]
        if explicit:
            return explicit
        if index == 0:
            return []
        return [steps[index - 1].id]

    def validate(self) -> None:
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        "workflow.dag_dangling_dependency",
                        f"Node '{node.node_id}' depends on unknown node '{dep}'.",
                        details={"node_id": node.node_id, "dependency": dep},
                    )
            for route_name, target in (("on_success", node.step.on_success), ("on_failure", node.step.on_failure)):
                if target and target not in self.nodes:
                    raise DomainError(
                        "workflow.dag_dangling_route",
                        f"Node '{node.node_id}' has {route_name} route to unknown node '{target}'.",
                        details={"node_id": node.node_id, "route": route_name, "target": target},
                    )
        self.topological_order()

    def topological_order(self) -> List[str]:
        visited: Dict[str, str] = {}
        ordered: List[str] = []

        def visit(node_id: str) -> None:
            state = visited.get(node_id)
            if state == "visiting":
                raise DomainError("workflow.dag_cycle", f"Cycle detected at workflow node '{node_id}'.")
            if state == "visited":
                return
            visited[node_id] = "visiting"
            for dep in self.nodes[node_id].dependencies:
                visit(dep)
            visited[node_id] = "visited"
            ordered.append(node_id)

        for node_id in self.order:
            visit(node_id)
        return ordered

    def ready_node_ids(self, *, completed: Set[str], running: Optional[Set[str]] = None, failed: Optional[Set[str]] = None) -> List[str]:
        running = running or set()
        failed = failed or set()
        ready: List[str] = []
        for node_id in self.topological_order():
            if node_id in completed or node_id in running or node_id in failed:
                continue
            node = self.nodes[node_id]
            if all(dep in completed for dep in node.dependencies):
                ready.append(node_id)
        return ready

    def route_for(self, node_id: str, result: Dict[str, Any]) -> Optional[str]:
        node = self.nodes[node_id]
        explicit_next = result.get("next_step_id") or result.get("next_node_id")
        if explicit_next:
            self.require_node(str(explicit_next))
            return str(explicit_next)
        status = str(result.get("status", "")).lower()
        if status in {"succeeded", "success", "pass", "passed"} and node.step.on_success:
            return node.step.on_success
        if status in {"failed", "failure", "blocked", "error"} and node.step.on_failure:
            return node.step.on_failure
        return None

    def downstream_node_ids(self, node_id: str) -> List[str]:
        self.require_node(node_id)
        return [candidate_id for candidate_id, node in self.nodes.items() if node_id in node.dependencies]

    def require_node(self, node_id: str) -> DAGRuntimeNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise DomainError("workflow.dag_unknown_node", f"Unknown workflow DAG node '{node_id}'.") from exc
