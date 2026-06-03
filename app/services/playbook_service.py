"""Playbook Service for Native 3.0 WorkItems.

This service replaces the legacy linear WorkflowEngine for 3.0 native playbooks.
"""
from typing import Dict, Any, Optional
from app.core.work import WorkItem, WorkStatus
from app.core.playbook import Playbook
from app.core.dag import TaskDAG, NodeStatus, DAGNode
from app.core.blackboard import Blackboard

class PlaybookService:
    def __init__(self, storage: Any = None, llm: Any = None):
        self.storage = storage
        self.llm = llm
        self.active_dags: Dict[str, TaskDAG] = {}
        self.blackboards: Dict[str, Blackboard] = {}

    def start_playbook(self, work_item: WorkItem, playbook: Playbook) -> None:
        """Initialize a DAG for a native playbook and start execution."""
        dag = TaskDAG(graph_id=work_item.work_id)
        
        # Convert playbook steps graph to DAGNodes
        for step in playbook.step_graph:
            node = DAGNode(
                node_id=step.get("id", "unknown"),
                action_type=step.get("type", "agent"),
                dependencies=step.get("depends_on", [])
            )
            dag.add_node(node)
            
        self.active_dags[work_item.work_id] = dag
        self.blackboards[work_item.work_id] = Blackboard()
        
        # Write initial context to blackboard
        self.blackboards[work_item.work_id].write("input_context", work_item.context_ref, owner_node="system")
        work_item.status = WorkStatus.RUNNING
        
        if self.storage:
            self.storage.save_work(work_item)

    def run_next(self, work_id: str) -> None:
        """Run the next executable nodes in the DAG."""
        dag = self.active_dags.get(work_id)
        if not dag:
            return
            
        blackboard = self.blackboards.get(work_id)
        
        ready_nodes = dag.get_executable_nodes()
        for node in ready_nodes:
            node.status = NodeStatus.RUNNING
            
            # TODO: Integrate real node execution logic based on ToolPolicy and action_type
            # For MVP, we simulate success
            if node.action_type == "gate":
                # Wait for user
                pass
            else:
                node.result = f"Output of {node.node_id}"
                node.status = NodeStatus.COMPLETED
                
                if blackboard:
                    blackboard.write(f"{node.node_id}_result", node.result, owner_node=node.node_id)
                    
        if dag.is_completed():
            # End of playbook
            pass
