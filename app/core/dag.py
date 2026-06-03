"""DAG Execution Graph for Evoloop 3.0 Playbooks."""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


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
