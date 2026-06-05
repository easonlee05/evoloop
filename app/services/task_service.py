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
    """任务生命周期管理与数据转换的应用服务。

    该类负责处理任务创建、运行、取消、删除等核心控制流，
    并提供将 1.0 版本的 Task 模型桥接/编译为 3.0 版本（WorkItem、ProductContext、ArtifactGraph）的接口。

    生命周期：
        通常在 Web 框架启动时作为单例被初始化，持有全局的 TaskDefinition 注册表、工作流引擎和持久化存储服务。
    """

    LEGACY_TYPE_ALIASES = {
        "manual": "legacy_manual",
        "legacy_manual": "legacy_manual",
        "prd": "legacy_prd",
        "legacy_prd": "legacy_prd",
    }

    def __init__(self, registry: Dict[str, TaskDefinition], engine: Any, storage: Any):
        """初始化任务服务。

        Args:
            registry: 任务定义的注册表，映射任务类型到具体 TaskDefinition。
            engine: 工作流引擎实例，用于执行和恢复任务。
            storage: 持久化存储层实例，支持加载/保存 TaskContext 与 Task 实例，附加事件等。
        """
        self.registry = registry
        self.engine = engine
        self.storage = storage
        self._running_tasks = set()

    def create_task(self, task_type: str, payload: Dict[str, Any]) -> Task:
        """创建新任务并保存初始上下文与任务实例。

        Args:
            task_type: 任务类型，支持 Legacy 别名标准化。
            payload: 创建任务所需的输入数据，包括 username, title, goal 等。

        Returns:
            Task: 初始化且状态为 CREATED 的 Task 实例。

        Raises:
            ValueError: 如果任务类型未知，或缺少 TaskDefinition 输入架构所要求的必需字段。
        """
        requested_task_type = task_type
        # 标准化任务类型，将 manual/prd 等映射为 legacy_manual/legacy_prd
        public_task_type = self._normalize_task_type(task_type)
        if public_task_type not in self.registry:
            raise ValueError(f"unknown task type: {task_type}")
        definition = self.registry[public_task_type]
        self._validate_required(definition, payload)
        
        task_id = f"task_{uuid4().hex[:12]}"
        
        # 尝试从 payload 中提取 title、goal、constraints 并设定默认回退值
        title = payload.get("title") or payload.get("feature") or payload.get("module_name") or payload.get("business_domain") or public_task_type
        goal = payload.get("goal") or payload.get("business_goal") or payload.get("instructions") or title
        constraints = payload.get("constraints") or payload.get("user_constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
            
        normalized_inputs = dict(payload)
        normalized_inputs.setdefault("requested_task_type", requested_task_type)
        normalized_inputs["task_type"] = public_task_type
        normalized_inputs["canonical_task_type"] = definition.type
        
        # 构建 1.0 的 TaskContext 上下文结构
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
        
        # 保存上下文与任务状态到持久化存储，并触发 task.created 事件
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
        """运行或恢复指定的任务。

        Args:
            task_id: 任务的唯一标识符。
            until_step_id: 任务运行的终止/暂停步骤节点标识符。

        Returns:
            Task: 运行/执行后的任务实例。
        """
        # 防止同一任务的并发执行，通过内存中的集合进行防重处理
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
        """为处于等待用户决策状态的任务应用决策，并将其恢复执行。

        Args:
            task_id: 任务的唯一标识符。
            decision: 用户所做的决策说明或裁决内容。
            selected_option: 用户选择的决策分支选项 ID。
            quoted_selections: 包含引用的具体文本片段/选择范围。

        Returns:
            Task: 应用决策并尝试运行后的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.apply_decision(
            task,
            decision=decision,
            selected_option=selected_option,
            quoted_selections=quoted_selections,
        )

    def cancel_task(self, task_id: str) -> Task:
        """取消一个执行中或挂起的任务。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 状态更新为已取消的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.cancel(task)

    def delete_task(self, task_id: str) -> Task:
        """对任务进行软删除（标记删除）。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 标记为已删除状态的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = True
        task.deleted_at = datetime.now().isoformat()
        self.storage.save_task(task)
        return task

    def restore_task(self, task_id: str) -> Task:
        """恢复被软删除的任务。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 取消删除标记的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = False
        task.deleted_at = None
        self.storage.save_task(task)
        return task

    def permanent_delete_task(self, task_id: str) -> None:
        """永久删除指定的任务目录（硬删除）。

        Args:
            task_id: 任务的唯一标识符。
        """
        if hasattr(self.storage, "delete_task_directory"):
            self.storage.delete_task_directory(task_id)

    def get_task(self, task_id: str) -> Task:
        """获取指定任务的实例。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 从存储加载的任务实例。
        """
        return self.storage.load_task(task_id, self.registry)

    def _validate_required(self, definition: TaskDefinition, payload: Dict[str, Any]) -> None:
        """验证 payload 是否提供了该任务定义所必需的入参。

        Args:
            definition: 任务定义规格。
            payload: 输入参数载荷。

        Raises:
            ValueError: 当缺少任何必需的入参字段时。
        """
        missing = [field for field in definition.input_schema.get("required", []) if not payload.get(field)]
        if missing:
            public_task_type = definition.metadata.get("public_task_type", definition.type)
            raise ValueError(f"missing required fields for {public_task_type}: {', '.join(missing)}")

    @classmethod
    def _normalize_task_type(cls, task_type: str) -> str:
        """将任务类型别名标准化为系统内的规范键值。

        Args:
            task_type: 待标准化的原始任务类型名称。

        Returns:
            str: 标准化后的规范任务类型。
        """
        return cls.LEGACY_TYPE_ALIASES.get(task_type, task_type)

    def get_work_item(self, task_id: str) -> WorkItem:
        """将 1.0 的 Task 转换为 3.0 的 WorkItem 状态实体。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            WorkItem: 3.0 版本的 WorkItem，包含转换后的状态映射与 Playbook 信息。
        """
        task = self.storage.load_task(task_id, self.registry)
        # 将 1.0 Task 状态映射到 3.0 的 WorkStatus
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
        
        # 兼容处理任务类型的转换
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
        """将 1.0 任务上下文及其关联信息，转换为 3.0 标准的 ProductContext。

        提取源材料、核心需求陈述、用户约束条件、已被裁决的 DecisionGate 列表等。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            ProductContext: 3.0 规范的产品上下文。
        """
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        # 转换输入材料 (SourceInput)
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
        
        # 转换业务需求 (Requirement)
        requirements = []
        primary_feature = (
            ctx.inputs.get("feature")
            or ctx.inputs.get("module_name")
            or ctx.inputs.get("business_intent")
        )
        if primary_feature:
            requirements.append(
                Requirement(
                    requirement_id="req_primary",
                    statement=str(primary_feature),
                    priority="must",
                    rationale=ctx.goal
                )
            )
        
        # 转换用户约束 (ProductConstraint)
        constraints = [
            ProductConstraint(
                constraint_id=f"const_{i}",
                statement=c,
                category="user"
            ) for i, c in enumerate(ctx.user_constraints)
        ]
        
        # 将已完成的决策（user_decisions）转换为 3.0 的决策门 (DecisionGate) 结构
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
            
        # 转换引用到的知识项（KnowledgeRef）
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
        """根据 1.0 的 artifacts 集合与决策状态构建 3.0 的 ArtifactGraph。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            ArtifactGraph: 3.0 规范的产物依赖关系图。
        """
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        nodes = []
        edges = []

        # 映射文件名称与 3.0 标准产物类型的关系
        native_type_map = {
            "machine_spec.yaml": ArtifactNodeType.MACHINE_SPEC,
            "human_brief.md": ArtifactNodeType.HUMAN_BRIEF,
            "agent_package_codex.md": ArtifactNodeType.AGENT_PACKAGE,
            "acceptance.md": ArtifactNodeType.ACCEPTANCE_PROTOCOL,
            "review_checklist.md": ArtifactNodeType.REVIEW_CHECKLIST,
            "traceability.json": ArtifactNodeType.TRACEABILITY_MAP,
            "review_result.md": ArtifactNodeType.REVIEW_RESULT,
            "PRD.md": ArtifactNodeType.OPTIONAL_PRD,
            "模块概览.md": ArtifactNodeType.OPTIONAL_MANUAL,
        }
        edge_type_map = {
            ArtifactNodeType.ACCEPTANCE_PROTOCOL: ArtifactEdgeType.VALIDATES,
            ArtifactNodeType.REVIEW_RESULT: ArtifactEdgeType.REVIEWS,
        }

        # 提取或初始化 MACHINE_SPEC (机器规格) 节点作为根/底座
        spec_node_id = None
        spec_artifact = next((art for art in ctx.artifacts if native_type_map.get(art.name) == ArtifactNodeType.MACHINE_SPEC), None)
        if spec_artifact:
            spec_node_id = f"node_art_{spec_artifact.artifact_id}"
            nodes.append(ArtifactNode(
                node_id=spec_node_id,
                type=ArtifactNodeType.MACHINE_SPEC,
                artifact_ref=ArtifactRef(
                    name=spec_artifact.name,
                    version=spec_artifact.version,
                    storage_uri=f"file://artifacts/{spec_artifact.artifact_id}",
                    checksum=getattr(spec_artifact, "checksum", None),
                ),
                summary="Native machine spec artifact",
                created_by=spec_artifact.created_by or "system",
            ))
        else:
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

        # 构建其他产物节点，并关联依赖（DERIVES_FROM 等边）
        for art in ctx.artifacts:
            if spec_artifact and art.artifact_id == spec_artifact.artifact_id:
                continue
            art_node_id = f"node_art_{art.artifact_id}"
            node_type = native_type_map.get(art.name)
            if node_type is None:
                projection_type_str = task.definition.metadata.get("legacy_projection")
                node_type = ArtifactNodeType.OPTIONAL_PRD
                if projection_type_str == "optional_manual":
                    node_type = ArtifactNodeType.OPTIONAL_MANUAL
            nodes.append(ArtifactNode(
                node_id=art_node_id,
                type=node_type,
                artifact_ref=ArtifactRef(
                    name=art.name,
                    version=art.version,
                    storage_uri=f"file://artifacts/{art.artifact_id}",
                    checksum=getattr(art, "checksum", None)
                ),
                summary=f"Artifact: {art.name}",
                created_by=art.created_by or "system"
            ))
            
            edges.append(ArtifactEdge(
                edge_id=f"edge_derive_{art.artifact_id}",
                from_node_id=art_node_id,
                to_node_id=spec_node_id,
                type=edge_type_map.get(node_type, ArtifactEdgeType.DERIVES_FROM),
                summary=f"{art.name} is linked to machine spec"
            ))
            
        # 构建决策节点，将用户决策映射进产物图
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
