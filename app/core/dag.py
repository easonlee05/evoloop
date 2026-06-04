"""DAG Execution Graph for Evoloop 3.0 Playbooks."""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.core.errors import DomainError


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DAGNode:
    node_id: str
    action_type: str  # e.g., 'agent', 'gate', 'artifact', 'system'
    status: NodeStatus = NodeStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None

    def is_ready(self, all_nodes: Dict[str, 'DAGNode']) -> bool:
        """Check if all dependencies are COMPLETED."""
        if self.status != NodeStatus.PENDING:
            return False
        for dep in self.dependencies:
            node = all_nodes.get(dep)
            if not node or node.status != NodeStatus.COMPLETED:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "action_type": self.action_type,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "conditions": self.conditions,
            "result": self.result
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAGNode":
        return cls(
            node_id=data["node_id"],
            action_type=data["action_type"],
            status=NodeStatus(data.get("status", "pending")),
            dependencies=list(data.get("dependencies", [])),
            conditions=dict(data.get("conditions", {})),
            result=data.get("result")
        )



@dataclass
class TaskDAG:
    graph_id: str
    nodes: Dict[str, DAGNode] = field(default_factory=dict)

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.node_id] = node

    def get_executable_nodes(self) -> List[DAGNode]:
        """Return nodes whose dependencies are met and are currently pending."""
        return [n for n in self.nodes.values() if n.is_ready(self.nodes)]

    def is_completed(self) -> bool:
        return all(n.status == NodeStatus.COMPLETED for n in self.nodes.values())

    def has_failed(self) -> bool:
        return any(n.status == NodeStatus.FAILED for n in self.nodes.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDAG":
        nodes_data = data.get("nodes", {})
        nodes = {nid: DAGNode.from_dict(ndata) for nid, ndata in nodes_data.items()}
        return cls(
            graph_id=data["graph_id"],
            nodes=nodes
        )

    def save_to_file(self, file_path: str) -> None:
        import json
        import yaml
        data = self.to_dict()
        if file_path.endswith((".yaml", ".yml")):
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str) -> "TaskDAG":
        import json
        import yaml
        if file_path.endswith((".yaml", ".yml")):
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        return cls.from_dict(data)

    def validate_dag(self) -> None:
        """Validate DAG constraints including dangling dependencies and cycles."""
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        code="dag.dangling_dependency",
                        message=f"Node '{node.node_id}' has dangling dependency on '{dep}'"
                    )
        self.get_topological_sort()

    def get_topological_sort(self) -> List[str]:
        """Return the topological sort order of the node IDs.
        
        Raises DomainError if dangling dependencies or cyclic dependencies are detected.
        """
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        code="dag.dangling_dependency",
                        message=f"Node '{node.node_id}' has dangling dependency on '{dep}'"
                    )

        visited = {}  # node_id -> state (1: visiting, 2: visited)
        order = []

        def dfs(node_id: str):
            state = visited.get(node_id, 0)
            if state == 1:
                raise DomainError(
                    code="dag.cyclic_dependency",
                    message=f"Cyclic dependency detected at node '{node_id}'"
                )
            if state == 2:
                return

            visited[node_id] = 1
            node = self.nodes[node_id]
            for dep in node.dependencies:
                dfs(dep)
            visited[node_id] = 2
            order.append(node_id)

        for node_id in self.nodes:
            dfs(node_id)
        return order
