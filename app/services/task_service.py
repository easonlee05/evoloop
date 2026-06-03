"""Application service for task creation, execution, decisions and cancellation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.context import TaskContext
from app.core.events import Event
from app.core.task import Task, TaskDefinition, TaskStatus

# 3.0 Frozen Contracts
from app.core.work import WorkItem, WorkType, WorkStatus
from app.core.playbook import (
    ProductContext, SourceInput, Requirement, ProductConstraint,
    DecisionGate, DecisionOption, GateResolution, DecisionGateStatus, KnowledgeRef
)
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactNodeType, ArtifactEdge, ArtifactEdgeType, ArtifactRef
)


class TaskService:
    LEGACY_TYPE_ALIASES = {
        "manual": "legacy_manual",
        "legacy_manual": "legacy_manual",
        "prd": "legacy_prd",
        "legacy_prd": "legacy_prd",
    }

    def __init__(self, registry: Dict[str, TaskDefinition], engine: Any, storage: Any):
        self.registry = registry
        self.engine = engine
        self.storage = storage
        self._running_tasks = set()

    def create_task(self, task_type: str, payload: Dict[str, Any]) -> Task:
        requested_task_type = task_type
        public_task_type = self._normalize_task_type(task_type)
        if public_task_type not in self.registry:
            raise ValueError(f"unknown task type: {task_type}")
        definition = self.registry[public_task_type]
        self._validate_required(definition, payload)
        task_id = f"task_{uuid4().hex[:12]}"
        title = payload.get("title") or payload.get("feature") or payload.get("module_name") or payload.get("business_domain") or public_task_type
        goal = payload.get("goal") or payload.get("business_goal") or payload.get("instructions") or title
        constraints = payload.get("constraints") or payload.get("user_constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        normalized_inputs = dict(payload)
        normalized_inputs.setdefault("requested_task_type", requested_task_type)
        normalized_inputs["task_type"] = public_task_type
        normalized_inputs["canonical_task_type"] = definition.type
        context = TaskContext(
            task_id=task_id,
            task_type=public_task_type,
            username=payload["username"],
            goal=goal,
            title=title,
            user_constraints=list(constraints),
            source_materials=[{"material_id": material_id} for material_id in payload.get("material_ids", [])],
            inputs=normalized_inputs,
        )
        task = Task(definition=definition, context=context, task_id=task_id, status=TaskStatus.CREATED)
        self.storage.save_context(context)
        self.storage.save_task(task)
        self.storage.append_event(
            Event(
                task_id=task_id,
                type="task.created",
                status=task.status.value,
                payload={
                    "task_type": public_task_type,
                    "canonical_task_type": definition.type,
                    "title": title,
                },
            )
        )
        return task

    def run_task(self, task_id: str, until_step_id: Optional[str] = None) -> Task:
        if task_id in self._running_tasks:
            return self.storage.load_task(task_id, self.registry)
        self._running_tasks.add(task_id)
        try:
            task = self.storage.load_task(task_id, self.registry)
            return self.engine.run(task, until_step_id=until_step_id)
        finally:
            self._running_tasks.discard(task_id)

    def apply_decision(
        self,
        task_id: str,
        decision: str,
        selected_option: Optional[str] = None,
        quoted_selections: Optional[list[dict[str, Any]]] = None,
    ) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.apply_decision(
            task,
            decision=decision,
            selected_option=selected_option,
            quoted_selections=quoted_selections,
        )

    def cancel_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.cancel(task)

    def delete_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = True
        task.deleted_at = datetime.now().isoformat()
        self.storage.save_task(task)
        return task

    def restore_task(self, task_id: str) -> Task:
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = False
        task.deleted_at = None
        self.storage.save_task(task)
        return task

    def permanent_delete_task(self, task_id: str) -> None:
        if hasattr(self.storage, "delete_task_directory"):
            self.storage.delete_task_directory(task_id)

    def get_task(self, task_id: str) -> Task:
        return self.storage.load_task(task_id, self.registry)

    def _validate_required(self, definition: TaskDefinition, payload: Dict[str, Any]) -> None:
        missing = [field for field in definition.input_schema.get("required", []) if not payload.get(field)]
        if missing:
            public_task_type = definition.metadata.get("public_task_type", definition.type)
            raise ValueError(f"missing required fields for {public_task_type}: {', '.join(missing)}")

    @classmethod
    def _normalize_task_type(cls, task_type: str) -> str:
        return cls.LEGACY_TYPE_ALIASES.get(task_type, task_type)

    def get_work_item(self, task_id: str) -> WorkItem:
        task = self.storage.load_task(task_id, self.registry)
        status_map = {
            TaskStatus.CREATED: WorkStatus.CREATED,
            TaskStatus.RUNNING: WorkStatus.RUNNING,
            TaskStatus.WAITING_FOR_USER: WorkStatus.WAITING_FOR_DECISION,
            TaskStatus.COMPLETED: WorkStatus.COMPLETED,
            TaskStatus.FAILED: WorkStatus.FAILED,
            TaskStatus.CANCELLED: WorkStatus.CANCELLED,
            TaskStatus.BLOCKED: WorkStatus.BLOCKED,
        }
        work_status = status_map.get(task.status, WorkStatus.CREATED)
        
        if task.definition.type == "prd":
            work_type = WorkType.LEGACY_PRD
        elif task.definition.type == "manual":
            work_type = WorkType.LEGACY_MANUAL
        else:
            try:
                work_type = WorkType(task.definition.type)
            except ValueError:
                work_type = WorkType.LEGACY_PRD

        return WorkItem(
            work_id=task.task_id,
            work_type=work_type,
            playbook_id=task.definition.workflow.name,
            title=task.context.title,
            objective=task.context.goal,
            workspace_id=task.task_id,
            product_context_ref=f"ctx_{task.task_id}",
            artifact_graph_ref=f"graph_{task.task_id}",
            status=work_status,
            current_decision_gate_id=task.waiting_step_id,
            metadata={
                "legacy_task_id": task.task_id,
                "legacy_bridge": True,
            }
        )

    def get_product_context(self, task_id: str) -> ProductContext:
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        source_inputs = []
        for i, mat in enumerate(ctx.source_materials):
            source_inputs.append(SourceInput(
                input_id=mat.get("material_id", f"mat_{i}"),
                kind="material",
                summary=f"Material input: {mat.get('material_id')}"
            ))
        source_inputs.append(SourceInput(
            input_id="payload_inputs",
            kind="inputs_payload",
            summary="Original task inputs payload",
            metadata=ctx.inputs
        ))
        
        requirements = []
        primary_feature = ctx.inputs.get("feature") or ctx.inputs.get("module_name")
        if primary_feature:
            requirements.append(
                Requirement(
                    requirement_id="req_primary",
                    statement=f"Feature/Module: {primary_feature}",
                    priority="must",
                    rationale=ctx.goal
                )
            )
        
        constraints = [
            ProductConstraint(
                constraint_id=f"const_{i}",
                statement=c,
                category="user"
            ) for i, c in enumerate(ctx.user_constraints)
        ]
        
        user_decisions = []
        for i, dec in enumerate(ctx.user_decisions):
            gate_id = f"gate_{i}"
            options = []
            if dec.selected_option:
                options.append(DecisionOption(
                    option_id=dec.selected_option,
                    label=f"Option {dec.selected_option}",
                    summary=dec.decision
                ))
            
            resolution = None
            if dec.selected_option:
                resolution = GateResolution(
                    selected_option_id=dec.selected_option,
                    rationale=dec.decision,
                    decided_by=ctx.username,
                )
            
            user_decisions.append(DecisionGate(
                gate_id=gate_id,
                work_id=task.task_id,
                question=dec.decision,
                options=options,
                impact_summary="Legacy user decision",
                blocking=True,
                status=DecisionGateStatus.RESOLVED if dec.selected_option else DecisionGateStatus.OPEN,
                resolution=resolution,
                metadata={
                    "quoted_selections": dec.quoted_selections,
                    "applies_to_step_id": dec.applies_to_step_id,
                    "resume_step_id": dec.resume_step_id,
                }
            ))
            
        knowledge_refs = []
        k_state = ctx.degradation_state.get("knowledge", {})
        if k_state and "preview" in k_state:
            for idx, item in enumerate(k_state.get("preview", [])):
                knowledge_refs.append(KnowledgeRef(
                    knowledge_id=f"kb_{idx}",
                    kind="retrieved_doc",
                    summary=item.get("summary", ""),
                    locator=item.get("title", "")
                ))
                
        return ProductContext(
            objective=ctx.goal,
            source_inputs=source_inputs,
            requirements=requirements,
            constraints=constraints,
            assumptions=[],
            user_decisions=user_decisions,
            knowledge_refs=knowledge_refs,
            worker_feedback=[],
            metadata={
                "username": ctx.username,
                "degradation_state": ctx.degradation_state,
                "inputs": ctx.inputs,
            }
        )

    def get_artifact_graph(self, task_id: str) -> ArtifactGraph:
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        nodes = []
        edges = []
        
        spec_node_id = f"node_spec_{task.task_id}"
        nodes.append(ArtifactNode(
            node_id=spec_node_id,
            type=ArtifactNodeType.MACHINE_SPEC,
            artifact_ref=ArtifactRef(
                name="machine_spec",
                storage_uri=f"memory://tasks/{task.task_id}/inputs"
            ),
            summary="Original task inputs and specifications",
            created_by="system"
        ))
        
        projection_type_str = task.definition.metadata.get("legacy_projection")
        node_type = ArtifactNodeType.OPTIONAL_PRD
        if projection_type_str == "optional_prd":
            node_type = ArtifactNodeType.OPTIONAL_PRD
        elif projection_type_str == "optional_manual":
            node_type = ArtifactNodeType.OPTIONAL_MANUAL
            
        for art in ctx.artifacts:
            art_node_id = f"node_art_{art.artifact_id}"
            nodes.append(ArtifactNode(
                node_id=art_node_id,
                type=node_type,
                artifact_ref=ArtifactRef(
                    name=art.name,
                    version=art.version,
                    storage_uri=f"file://artifacts/{art.artifact_id}",
                    checksum=getattr(art, "checksum", None)
                ),
                summary=f"Legacy artifact: {art.name}",
                created_by=art.created_by or "system"
            ))
            
            edges.append(ArtifactEdge(
                edge_id=f"edge_derive_{art.artifact_id}",
                from_node_id=art_node_id,
                to_node_id=spec_node_id,
                type=ArtifactEdgeType.DERIVES_FROM,
                summary="Legacy projection derives from machine spec"
            ))
            
        for idx, dec in enumerate(ctx.user_decisions):
            dec_node_id = f"node_dec_{idx}_{task.task_id}"
            nodes.append(ArtifactNode(
                node_id=dec_node_id,
                type=ArtifactNodeType.DECISION,
                artifact_ref=ArtifactRef(
                    name=f"decision_{idx}",
                    storage_uri=f"memory://tasks/{task.task_id}/decision_{idx}"
                ),
                summary=f"User decision: {dec.decision}",
                created_by=ctx.username
            ))
            
            edges.append(ArtifactEdge(
                edge_id=f"edge_dec_{idx}",
                from_node_id=spec_node_id,
                to_node_id=dec_node_id,
                type=ArtifactEdgeType.RESOLVES_DECISION,
                summary="Machine spec resolves user decision"
            ))
            
        graph = ArtifactGraph(
            work_id=task.task_id,
            nodes=nodes,
            edges=edges
        )
        graph.validate()
        return graph
