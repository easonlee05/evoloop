"""Unit tests for Evoloop 3.0 Contracts."""
import unittest
from uuid import uuid4

from app.core.work import WorkItem, WorkType, WorkStatus
from app.core.playbook import (
    Playbook, PlaybookStep, ProductContext, DecisionGate, WorkerAdapter,
    SourceInput, Requirement, ProductConstraint, ProductAssumption,
    KnowledgeRef, WorkerFeedback, DecisionOption, GateResolution,
    DecisionGateStatus, WorkerTargetType
)
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
    ArtifactNodeType, ArtifactEdgeType, ArtifactGraphValidationError
)
from app.core.review import (
    ReviewResult, RequirementCoverage, ReviewIssue, ReviewFixTask,
    ReviewVerdict, ReviewIssueSeverity
)
from app.services.playbook_service import PlaybookService


class TestContractsLane(unittest.TestCase):
    def test_work_item_serialization(self):
        item = WorkItem(
            work_type=WorkType.SPEC_TO_AGENT,
            playbook_id="playbook_123",
            title="Test Work Item",
            objective="Verify WorkItem contracts",
            workspace_id="workspace_abc",
            product_context_ref="ctx_ref_001",
            artifact_graph_ref="graph_ref_001",
            status=WorkStatus.CREATED
        )
        d = item.to_dict()
        self.assertEqual(d["work_type"], "spec_to_agent")
        self.assertEqual(d["status"], "created")
        self.assertEqual(d["playbook_id"], "playbook_123")

        item2 = WorkItem.from_dict(d)
        self.assertEqual(item2.work_id, item.work_id)
        self.assertEqual(item2.work_type, WorkType.SPEC_TO_AGENT)
        self.assertEqual(item2.title, "Test Work Item")
        self.assertEqual(item2.product_context_ref, "ctx_ref_001")

    def test_playbook_serialization(self):
        step = PlaybookStep(
            step_id="step_1",
            title="Step One",
            purpose="Generate Spec",
            allowed_tools=["material.read"],
            produces_artifact_types=["machine_spec"],
            next_step_ids=["step_2"]
        )
        playbook = Playbook(
            playbook_id="playbook_v3_spec",
            version="3.0",
            trigger_types=["intent"],
            steps=[step],
            allowed_tools=["material.read", "artifact.write"],
            output_artifact_types=["machine_spec", "agent_package"]
        )
        d = playbook.to_dict()
        self.assertEqual(d["playbook_id"], "playbook_v3_spec")
        self.assertEqual(d["steps"][0]["step_id"], "step_1")

        playbook2 = Playbook.from_dict(d)
        self.assertEqual(playbook2.playbook_id, "playbook_v3_spec")
        self.assertEqual(len(playbook2.steps), 1)
        self.assertEqual(playbook2.steps[0].title, "Step One")

    def test_product_context_serialization(self):
        ctx = ProductContext(
            objective="Test Objective",
            source_inputs=[SourceInput(input_id="in_1", kind="brief", summary="Brief details")],
            requirements=[Requirement(requirement_id="req_1", statement="Must support SSO")],
            constraints=[ProductConstraint(constraint_id="const_1", statement="No external DBs")],
            assumptions=[ProductAssumption(assumption_id="asmp_1", statement="Internet is up")],
            knowledge_refs=[KnowledgeRef(knowledge_id="kn_1", kind="api", summary="API spec")],
            worker_feedback=[WorkerFeedback(feedback_id="fb_1", worker_id="codex", summary="Done")]
        )
        d = ctx.to_dict()
        self.assertEqual(d["objective"], "Test Objective")
        self.assertEqual(d["requirements"][0]["requirement_id"], "req_1")

        ctx2 = ProductContext.from_dict(d)
        self.assertEqual(ctx2.objective, "Test Objective")
        self.assertEqual(ctx2.requirements[0].statement, "Must support SSO")
        self.assertEqual(ctx2.constraints[0].statement, "No external DBs")
        self.assertEqual(ctx2.assumptions[0].statement, "Internet is up")

    def test_decision_gate_serialization(self):
        option = DecisionOption(option_id="opt_a", label="Option A", summary="Choose A")
        resolution = GateResolution(selected_option_id="opt_a", rationale="Simplest option")
        gate = DecisionGate(
            gate_id="gate_1",
            work_id="work_1",
            question="Which flow?",
            options=[option],
            impact_summary="High impact",
            blocking=True,
            status=DecisionGateStatus.OPEN,
            resolution=resolution
        )
        d = gate.to_dict()
        self.assertEqual(d["gate_id"], "gate_1")
        self.assertEqual(d["resolution"]["selected_option_id"], "opt_a")

        gate2 = DecisionGate.from_dict(d)
        self.assertEqual(gate2.gate_id, "gate_1")
        self.assertEqual(gate2.options[0].label, "Option A")
        self.assertEqual(gate2.resolution.rationale, "Simplest option")

    def test_worker_adapter_serialization(self):
        adapter = WorkerAdapter(
            adapter_id="adapter_claude",
            target_type=WorkerTargetType.CLAUDE_CODE,
            package_format="markdown",
            invocation_policy={"timeout": 60},
            result_intake_policy={"format": "diff"}
        )
        d = adapter.to_dict()
        self.assertEqual(d["adapter_id"], "adapter_claude")
        self.assertEqual(d["target_type"], "claude_code")

        adapter2 = WorkerAdapter.from_dict(d)
        self.assertEqual(adapter2.adapter_id, "adapter_claude")
        self.assertEqual(adapter2.target_type, WorkerTargetType.CLAUDE_CODE)
        self.assertEqual(adapter2.package_format, "markdown")

    def test_review_result_serialization(self):
        coverage = RequirementCoverage(requirement_id="req_1", covered=True, evidence_refs=["log_1"])
        issue = ReviewIssue(issue_id="issue_1", severity=ReviewIssueSeverity.MAJOR, summary="Security leak")
        fix_task = ReviewFixTask(task_id="fix_1", title="Sanitize input", source_issue_ids=["issue_1"])
        result = ReviewResult(
            work_id="work_1",
            machine_spec_ref="spec_1",
            verdict=ReviewVerdict.CHANGES_REQUIRED,
            summary="Needs changes",
            coverage=[coverage],
            issues=[issue],
            fix_tasks=[fix_task],
            acceptance_protocol_ref="protocol_1"
        )
        d = result.to_dict()
        self.assertEqual(d["verdict"], "changes_required")
        self.assertEqual(d["coverage"][0]["requirement_id"], "req_1")
        self.assertEqual(d["issues"][0]["summary"], "Security leak")
        self.assertEqual(d["fix_tasks"][0]["title"], "Sanitize input")

        result2 = ReviewResult.from_dict(d)
        self.assertEqual(result2.work_id, "work_1")
        self.assertEqual(result2.verdict, ReviewVerdict.CHANGES_REQUIRED)
        self.assertEqual(result2.coverage[0].covered, True)
        self.assertEqual(result2.issues[0].severity, ReviewIssueSeverity.MAJOR)
        self.assertEqual(result2.fix_tasks[0].source_issue_ids, ["issue_1"])

    def test_artifact_graph_validation_success(self):
        spec_ref = ArtifactRef(name="machine_spec.yaml", storage_uri="s3://specs/1")
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        package_ref = ArtifactRef(name="package.md", storage_uri="s3://packages/1")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        package_node = ArtifactNode(node_id="n_package", type=ArtifactNodeType.AGENT_PACKAGE, artifact_ref=package_ref)

        edge1 = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        edge2 = ArtifactEdge(edge_id="e2", from_node_id="n_package", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)

        graph = ArtifactGraph(
            work_id="work_1",
            nodes=[spec_node, prd_node, package_node],
            edges=[edge1, edge2]
        )
        # 应该通过校验，不抛出异常
        graph.validate()
        self.assertEqual(graph.source_of_truth_node().node_id, "n_spec")

    def test_artifact_graph_validation_no_machine_spec_with_projections(self):
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        graph = ArtifactGraph(work_id="work_1", nodes=[prd_node], edges=[])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("must contain exactly one machine_spec", str(context.exception))

    def test_artifact_graph_validation_multiple_machine_specs(self):
        spec_ref1 = ArtifactRef(name="machine_spec1.yaml")
        spec_ref2 = ArtifactRef(name="machine_spec2.yaml")

        spec_node1 = ArtifactNode(node_id="n_spec1", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref1)
        spec_node2 = ArtifactNode(node_id="n_spec2", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref2)

        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node1, spec_node2], edges=[])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("must contain exactly one machine_spec", str(context.exception))

    def test_artifact_graph_validation_unconnected_projection_node(self):
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        # 没有边连接 prd_node 和 spec_node
        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, prd_node], edges=[])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("is disconnected from the machine_spec source of truth", str(context.exception))

    def test_artifact_graph_validation_reverse_dependence_on_projection(self):
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")

        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)

        # 错误依赖：machine_spec 衍生自 prd（真相源不能衍生自投影）
        bad_edge = ArtifactEdge(
            edge_id="e_bad",
            from_node_id="n_spec",
            to_node_id="n_prd",
            type=ArtifactEdgeType.DERIVES_FROM
        )

        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, prd_node], edges=[bad_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("is invalid because the source of truth cannot derive from", str(context.exception))

    def test_artifact_graph_cycle_detection(self):
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        prd_ref = ArtifactRef(name="PRD.md")
        brief_ref = ArtifactRef(name="human_brief.md")
        
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        brief_node = ArtifactNode(node_id="n_brief", type=ArtifactNodeType.HUMAN_BRIEF, artifact_ref=brief_ref)
        
        # 形成有向循环依赖（brief -> prd -> brief）并连上 n_spec
        edge_init = ArtifactEdge(edge_id="e_init", from_node_id="n_brief", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        edge1 = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_brief", type=ArtifactEdgeType.DERIVES_FROM)
        edge2 = ArtifactEdge(edge_id="e2", from_node_id="n_brief", to_node_id="n_prd", type=ArtifactEdgeType.DERIVES_FROM)
        
        graph = ArtifactGraph(work_id="work_loop", nodes=[spec_node, prd_node, brief_node], edges=[edge_init, edge1, edge2])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("contains a dependency loop/cycle", str(context.exception))

    def test_artifact_graph_edge_type_constraints(self):
        from app.core.artifact_graph import (
            ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
            ArtifactNodeType, ArtifactEdgeType, ArtifactGraphValidationError
        )
        
        spec_ref = ArtifactRef(name="machine_spec.yaml")
        req_ref = ArtifactRef(name="req_1")
        review_ref = ArtifactRef(name="review.md")
        decision_ref = ArtifactRef(name="dec_1")
        acceptance_ref = ArtifactRef(name="acc_1")
        checklist_ref = ArtifactRef(name="chk_1")
        
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        req_node = ArtifactNode(node_id="n_req", type=ArtifactNodeType.REQUIREMENT, artifact_ref=req_ref)
        review_node = ArtifactNode(node_id="n_review", type=ArtifactNodeType.REVIEW_RESULT, artifact_ref=review_ref)
        decision_node = ArtifactNode(node_id="n_dec", type=ArtifactNodeType.DECISION, artifact_ref=decision_ref)
        acceptance_node = ArtifactNode(node_id="n_acc", type=ArtifactNodeType.ACCEPTANCE_PROTOCOL, artifact_ref=acceptance_ref)
        checklist_node = ArtifactNode(node_id="n_chk", type=ArtifactNodeType.REVIEW_CHECKLIST, artifact_ref=checklist_ref)
        
        # 1. 错误的依赖：将 reviews 边错误地从 requirement 指向 spec_node（reviews 应该从 review_result 出发）
        bad_edge = ArtifactEdge(
            edge_id="e_bad_review",
            from_node_id="n_req",
            to_node_id="n_spec",
            type=ArtifactEdgeType.REVIEWS
        )
        graph = ArtifactGraph(work_id="work_1", nodes=[spec_node, req_node], edges=[bad_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph.validate()
        self.assertIn("Edge 'e_bad_review' type 'reviews' is incompatible", str(context.exception))
        
        # 2. 正确的依赖：从 review_node 指向 spec_node 应该是 reviews 关系
        good_edge = ArtifactEdge(
            edge_id="e_good_review",
            from_node_id="n_review",
            to_node_id="n_spec",
            type=ArtifactEdgeType.REVIEWS
        )
        # 应该成功，不抛出异常
        graph_ok = ArtifactGraph(work_id="work_2", nodes=[spec_node, review_node], edges=[good_edge])
        graph_ok.validate()

        # 3. VALIDATES 约束验证
        # 3a. 错误情况：VALIDATES 从 requirement 出发（VALIDATES source 必须是 acceptance_protocol 或 review_checklist）
        bad_validate_edge = ArtifactEdge(
            edge_id="e_bad_validate",
            from_node_id="n_req",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_bad_validate = ArtifactGraph(work_id="work_3a", nodes=[spec_node, req_node], edges=[bad_validate_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_validate.validate()
        self.assertIn("Edge 'e_bad_validate' type 'validates' is incompatible", str(context.exception))

        # 3b. 正确情况：VALIDATES 从 acceptance_protocol 出发
        good_validate_edge_1 = ArtifactEdge(
            edge_id="e_good_validate_1",
            from_node_id="n_acc",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_good_validate_1 = ArtifactGraph(work_id="work_3b", nodes=[spec_node, acceptance_node], edges=[good_validate_edge_1])
        graph_good_validate_1.validate()

        # 3c. 正确情况：VALIDATES 从 review_checklist 出发
        good_validate_edge_2 = ArtifactEdge(
            edge_id="e_good_validate_2",
            from_node_id="n_chk",
            to_node_id="n_spec",
            type=ArtifactEdgeType.VALIDATES
        )
        graph_good_validate_2 = ArtifactGraph(work_id="work_3c", nodes=[spec_node, checklist_node], edges=[good_validate_edge_2])
        graph_good_validate_2.validate()

        # 4. ADDRESSES_REQUIREMENT 约束验证
        # 4a. 错误情况：ADDRESSES_REQUIREMENT 指向 decision 节点（ADDRESSES_REQUIREMENT target 必须是 requirement）
        bad_addr_edge = ArtifactEdge(
            edge_id="e_bad_addr",
            from_node_id="n_spec",
            to_node_id="n_dec",
            type=ArtifactEdgeType.ADDRESSES_REQUIREMENT
        )
        graph_bad_addr = ArtifactGraph(work_id="work_4a", nodes=[spec_node, decision_node], edges=[bad_addr_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_addr.validate()
        self.assertIn("Edge 'e_bad_addr' type 'addresses_requirement' is incompatible", str(context.exception))

        # 4b. 正确情况：ADDRESSES_REQUIREMENT 指向 requirement
        good_addr_edge = ArtifactEdge(
            edge_id="e_good_addr",
            from_node_id="n_spec",
            to_node_id="n_req",
            type=ArtifactEdgeType.ADDRESSES_REQUIREMENT
        )
        graph_good_addr = ArtifactGraph(work_id="work_4b", nodes=[spec_node, req_node], edges=[good_addr_edge])
        graph_good_addr.validate()

        # 5. RESOLVES_DECISION 约束验证
        # 5a. 错误情况：RESOLVES_DECISION 指向 requirement 节点（RESOLVES_DECISION target 必须是 decision）
        bad_resol_edge = ArtifactEdge(
            edge_id="e_bad_resol",
            from_node_id="n_spec",
            to_node_id="n_req",
            type=ArtifactEdgeType.RESOLVES_DECISION
        )
        graph_bad_resol = ArtifactGraph(work_id="work_5a", nodes=[spec_node, req_node], edges=[bad_resol_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_resol.validate()
        self.assertIn("Edge 'e_bad_resol' type 'resolves_decision' is incompatible", str(context.exception))

        # 5b. 正确情况：RESOLVES_DECISION 指向 decision
        good_resol_edge = ArtifactEdge(
            edge_id="e_good_resol",
            from_node_id="n_spec",
            to_node_id="n_dec",
            type=ArtifactEdgeType.RESOLVES_DECISION
        )
        graph_good_resol = ArtifactGraph(work_id="work_5b", nodes=[spec_node, decision_node], edges=[good_resol_edge])
        graph_good_resol.validate()

        # 6. SUPERSEDES 约束验证
        # 6a. 错误情况：SUPERSEDES 的两个节点类型不一致（一个 requirement，一个 decision）
        bad_supersedes_edge = ArtifactEdge(
            edge_id="e_bad_supersedes",
            from_node_id="n_req",
            to_node_id="n_dec",
            type=ArtifactEdgeType.SUPERSEDES
        )
        graph_bad_supersedes = ArtifactGraph(work_id="work_6a", nodes=[spec_node, req_node, decision_node], edges=[bad_supersedes_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_bad_supersedes.validate()
        self.assertIn("Edge 'e_bad_supersedes' type 'supersedes' is incompatible", str(context.exception))

        # 6b. 正确情况：SUPERSEDES 的两个节点类型一致（都是 requirement）
        req_ref_2 = ArtifactRef(name="req_2")
        req_node_2 = ArtifactNode(node_id="n_req_2", type=ArtifactNodeType.REQUIREMENT, artifact_ref=req_ref_2)
        good_supersedes_edge = ArtifactEdge(
            edge_id="e_good_supersedes",
            from_node_id="n_req_2",
            to_node_id="n_req",
            type=ArtifactEdgeType.SUPERSEDES
        )
        graph_good_supersedes = ArtifactGraph(work_id="work_6b", nodes=[spec_node, req_node, req_node_2], edges=[good_supersedes_edge])
        graph_good_supersedes.validate()

        # 7. 悬挂边 (Dangling Edge) 校验
        # 7a. from_node 不存在
        dangling_from_edge = ArtifactEdge(
            edge_id="e_dangling_from",
            from_node_id="n_non_existent",
            to_node_id="n_spec",
            type=ArtifactEdgeType.DERIVES_FROM
        )
        graph_dangling_from = ArtifactGraph(work_id="work_7a", nodes=[spec_node], edges=[dangling_from_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_dangling_from.validate()
        self.assertIn("referencing non-existent node", str(context.exception))

        # 7b. to_node 不存在
        dangling_to_edge = ArtifactEdge(
            edge_id="e_dangling_to",
            from_node_id="n_spec",
            to_node_id="n_non_existent",
            type=ArtifactEdgeType.DERIVES_FROM
        )
        graph_dangling_to = ArtifactGraph(work_id="work_7b", nodes=[spec_node], edges=[dangling_to_edge])
        with self.assertRaises(ArtifactGraphValidationError) as context:
            graph_dangling_to.validate()
        self.assertIn("referencing non-existent node", str(context.exception))

    def test_playbook_service_uses_frozen_contract_field_names(self):
        item = WorkItem(
            work_type=WorkType.SPEC_TO_AGENT,
            playbook_id="playbook_v3_spec",
            title="Spec Work",
            objective="Compile intent",
            workspace_id="workspace_1",
            product_context_ref="ctx_ref_001",
            artifact_graph_ref="graph_ref_001",
        )
        playbook = Playbook(
            playbook_id="playbook_v3_spec",
            version="3.0",
            trigger_types=["intent"],
            steps=[
                PlaybookStep(
                    step_id="step_1",
                    title="Step One",
                    purpose="Generate Spec",
                    next_step_ids=["step_2"],
                )
            ],
        )

        service = PlaybookService()
        service.start_playbook(item, playbook)

        self.assertIn(item.work_id, service.active_dags)
        self.assertIn(item.work_id, service.blackboards)
        self.assertEqual(item.status, WorkStatus.RUNNING)

    def test_blackboard_slot_permission_and_type_safety(self):
        from app.core.blackboard import Blackboard, BlackboardSlot

        blackboard = Blackboard()
        slot = BlackboardSlot(
            key="config_slot",
            data_type=dict,
            allowed_writers=["admin_node"],
            allowed_readers=["admin_node", "audit_node"]
        )
        blackboard.register_slot(slot)

        # 1. 验证正常读写
        blackboard.write("config_slot", {"theme": "dark"}, caller_id="admin_node")
        val = blackboard.read("config_slot", caller_id="admin_node")
        self.assertEqual(val, {"theme": "dark"})

        # 2. 动态类型错误拦截
        with self.assertRaises(TypeError):
            blackboard.write("config_slot", "not-a-dict", caller_id="admin_node")

        # 3. 越权写入校验
        with self.assertRaises(PermissionError):
            blackboard.write("config_slot", {"theme": "light"}, caller_id="guest_node")

        # 4. 越权读取校验
        with self.assertRaises(PermissionError):
            blackboard.read("config_slot", caller_id="guest_node")

        # 5. 审计节点可读但不可写
        val_audit = blackboard.read("config_slot", caller_id="audit_node")
        self.assertEqual(val_audit, {"theme": "dark"})
        with self.assertRaises(PermissionError):
            blackboard.write("config_slot", {"theme": "light"}, caller_id="audit_node")

    def test_task_dag_deep_validation_and_topological_sort(self):
        from app.core.dag import TaskDAG, DAGNode
        from app.core.errors import DomainError

        # 1. 验证正常 DAG 及其拓扑排序
        dag = TaskDAG(graph_id="normal_dag")
        node_a = DAGNode(node_id="A", action_type="agent")
        node_b = DAGNode(node_id="B", action_type="agent", dependencies=["A"])
        node_c = DAGNode(node_id="C", action_type="agent", dependencies=["B"])
        
        dag.add_node(node_a)
        dag.add_node(node_b)
        dag.add_node(node_c)

        dag.validate_dag()
        sort_order = dag.get_topological_sort()
        self.assertEqual(sort_order, ["A", "B", "C"])

        # 2. 验证悬挂边校验
        dag_dangling = TaskDAG(graph_id="dangling_dag")
        node_x = DAGNode(node_id="X", action_type="agent")
        node_y = DAGNode(node_id="Y", action_type="agent", dependencies=["Z"])
        dag_dangling.add_node(node_x)
        dag_dangling.add_node(node_y)

        with self.assertRaises(DomainError) as ctx:
            dag_dangling.validate_dag()
        self.assertEqual(ctx.exception.code, "dag.dangling_dependency")

        with self.assertRaises(DomainError) as ctx_sort:
            dag_dangling.get_topological_sort()
        self.assertEqual(ctx_sort.exception.code, "dag.dangling_dependency")

        # 3. 验证循环依赖校验
        dag_cycle = TaskDAG(graph_id="cyclic_dag")
        node_m = DAGNode(node_id="M", action_type="agent", dependencies=["N"])
        node_n = DAGNode(node_id="N", action_type="agent", dependencies=["M"])
        dag_cycle.add_node(node_m)
        dag_cycle.add_node(node_n)

        with self.assertRaises(DomainError) as ctx_cycle:
            dag_cycle.validate_dag()
        self.assertEqual(ctx_cycle.exception.code, "dag.cyclic_dependency")

        with self.assertRaises(DomainError) as ctx_cycle_sort:
            dag_cycle.get_topological_sort()
        self.assertEqual(ctx_cycle_sort.exception.code, "dag.cyclic_dependency")

    def test_strong_type_file_persistence(self):
        import tempfile
        import os
        from app.core.playbook import (
            ProductContext, SourceInput, Requirement, ProductConstraint,
            ProductAssumption, KnowledgeRef, WorkerFeedback, DecisionOption,
            DecisionGate, GateResolution
        )
        from app.core.artifact_graph import (
            ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactRef,
            ArtifactNodeType, ArtifactEdgeType
        )

        # 1. 构造一个包含丰富属性的 ProductContext
        option = DecisionOption(option_id="opt_1", label="Opt 1", summary="summary opt")
        resolution = GateResolution(selected_option_id="opt_1", rationale="rat")
        gate = DecisionGate(
            gate_id="gate_1",
            work_id="work_1",
            question="Q?",
            options=[option],
            impact_summary="impact",
            resolution=resolution
        )
        ctx = ProductContext(
            objective="Test Objective",
            source_inputs=[SourceInput(input_id="in_1", kind="brief", summary="Brief details")],
            requirements=[Requirement(requirement_id="req_1", statement="Must support SSO")],
            constraints=[ProductConstraint(constraint_id="const_1", statement="No external DBs")],
            assumptions=[ProductAssumption(assumption_id="asmp_1", statement="Internet is up")],
            user_decisions=[gate],
            knowledge_refs=[KnowledgeRef(knowledge_id="kn_1", kind="api", summary="API spec")],
            worker_feedback=[WorkerFeedback(feedback_id="fb_1", worker_id="codex", summary="Done")]
        )

        # 2. 构造一个包含丰富属性的 ArtifactGraph
        spec_ref = ArtifactRef(name="machine_spec.yaml", storage_uri="s3://specs/1")
        prd_ref = ArtifactRef(name="PRD.md", storage_uri="s3://prds/1")
        spec_node = ArtifactNode(node_id="n_spec", type=ArtifactNodeType.MACHINE_SPEC, artifact_ref=spec_ref)
        prd_node = ArtifactNode(node_id="n_prd", type=ArtifactNodeType.OPTIONAL_PRD, artifact_ref=prd_ref)
        edge = ArtifactEdge(edge_id="e1", from_node_id="n_prd", to_node_id="n_spec", type=ArtifactEdgeType.DERIVES_FROM)
        
        graph = ArtifactGraph(
            work_id="work_1",
            nodes=[spec_node, prd_node],
            edges=[edge]
        )

        fd_ctx, temp_path_ctx = tempfile.mkstemp(suffix=".json")
        fd_graph, temp_path_graph = tempfile.mkstemp(suffix=".json")
        os.close(fd_ctx)
        os.close(fd_graph)

        try:
            # 持久化
            ctx.save_to_file(temp_path_ctx)
            graph.save_to_file(temp_path_graph)

            # 加载
            loaded_ctx = ProductContext.load_from_file(temp_path_ctx)
            loaded_graph = ArtifactGraph.load_from_file(temp_path_graph)

            # 断言内容 100% 一致
            self.assertEqual(ctx.to_dict(), loaded_ctx.to_dict())
            self.assertEqual(graph.to_dict(), loaded_graph.to_dict())

            # 验证类型
            self.assertIsInstance(loaded_ctx, ProductContext)
            self.assertIsInstance(loaded_graph, ArtifactGraph)

        finally:
            if os.path.exists(temp_path_ctx):
                os.remove(temp_path_ctx)
            if os.path.exists(temp_path_graph):
                os.remove(temp_path_graph)

    def test_blackboard_dynamic_loading_and_audit(self):
        from app.core.blackboard import Blackboard
        blackboard = Blackboard()
        
        # 1. 测试从字典动态加载槽定义
        slot_data = [
            {
                "key": "dynamic_int",
                "data_type": "int",
                "allowed_writers": ["writer_a"],
                "allowed_readers": ["reader_b"]
            },
            {
                "key": "dynamic_list",
                "data_type": "list",
                "allowed_writers": ["writer_c"]
            }
        ]
        blackboard.load_slots_from_dict(slot_data)
        
        # 验证是否正确解析并注册了槽
        self.assertIn("dynamic_int", blackboard._slots)
        self.assertEqual(blackboard._slots["dynamic_int"].data_type, int)
        
        # 2. 测试拦截审计回调
        audit_events = []
        def mock_audit_callback(caller_id, action, key, success, error_message=None):
            audit_events.append((caller_id, action, key, success))
            
        blackboard.set_audit_callback(mock_audit_callback)
        
        # 正常写入
        blackboard.write("dynamic_int", 42, caller_id="writer_a")
        # 越权写入
        with self.assertRaises(PermissionError):
            blackboard.write("dynamic_int", 99, caller_id="malicious_user")
            
        # 校验审计日志中记录了上述尝试
        self.assertEqual(len(audit_events), 2)
        self.assertEqual(audit_events[0], ("writer_a", "write", "dynamic_int", True))
        self.assertEqual(audit_events[1], ("malicious_user", "write", "dynamic_int", False))

    def test_blackboard_improvements(self):
        from app.core.blackboard import Blackboard, BlackboardSlot
        from typing import Union

        # 1. 测试匿名读取（caller_id=None）时，审计日志中记录 caller 为 "system"
        blackboard = Blackboard()
        audit_events = []
        def mock_audit_callback(caller_id, action, key, success, error_message=None):
            audit_events.append((caller_id, action, key, success))
        blackboard.set_audit_callback(mock_audit_callback)

        blackboard.write("some_key", "some_value")  # 默认 caller_id = None -> system
        self.assertEqual(blackboard.read("some_key"), "some_value")
        self.assertEqual(audit_events[0], ("system", "write", "some_key", True))
        self.assertEqual(audit_events[1], ("system", "read", "some_key", True))

        # 2. 测试复杂 Union 类型不崩溃且有效拦截无效类型（Union[int, str]）
        slot_union = BlackboardSlot(
            key="union_slot",
            data_type=Union[int, str]
        )
        blackboard.register_slot(slot_union)
        # 应该正常写入，不会触发 TypeError
        blackboard.write("union_slot", 42)
        blackboard.write("union_slot", "hello")
        self.assertEqual(blackboard.read("union_slot"), "hello")
        # 应该拦截无效的类型写入
        with self.assertRaises(TypeError):
            blackboard.write("union_slot", 4.5)

        # 3. 严格模式 (strict=True) 拦截未注册 slot 的读写
        strict_bb = Blackboard(strict=True)
        # 写入未注册 key 应该抛出 KeyError
        with self.assertRaises(KeyError):
            strict_bb.write("unregistered_key", "value")
        # 读取未注册 key 应该抛出 KeyError
        with self.assertRaises(KeyError):
            strict_bb.read("unregistered_key")

        # 注册后再读写则正常
        slot_ok = BlackboardSlot(key="registered_key", data_type=str)
        strict_bb.register_slot(slot_ok)
        strict_bb.write("registered_key", "value")
        self.assertEqual(strict_bb.read("registered_key"), "value")

        # 4. 测试审计回调异常不崩溃，并且不会中断主执行流
        bad_events = []
        def bad_audit_callback(caller_id, action, key, success, error_message=None):
            bad_events.append((caller_id, action, key, success))
            raise ValueError("Audit logger failed!")
        
        blackboard.set_audit_callback(bad_audit_callback)
        # 即使 audit 触发 ValueError，这里的 write 也应该成功执行，不会抛出异常
        blackboard.write("registered_key", "new_value")
        self.assertEqual(blackboard.read("registered_key"), "new_value")

    def test_task_dag_conditions_and_serialization(self):
        from app.core.dag import TaskDAG, DAGNode, NodeStatus
        import tempfile
        import os
        
        # 1. 验证条件边属性
        node = DAGNode(
            node_id="step_conditional",
            action_type="agent",
            conditions={"blackboard.decision": "agree"}
        )
        self.assertEqual(node.conditions.get("blackboard.decision"), "agree")
        
        # 2. 验证 DAG 的 to_dict / from_dict / save_to_file / load_from_file
        dag = TaskDAG(graph_id="dag_serial_test")
        node_a = DAGNode(node_id="A", action_type="agent", status=NodeStatus.COMPLETED)
        node_b = DAGNode(
            node_id="B",
            action_type="agent",
            dependencies=["A"],
            conditions={"key": "val"}
        )
        dag.add_node(node_a)
        dag.add_node(node_b)
        
        d = dag.to_dict()
        self.assertEqual(d["graph_id"], "dag_serial_test")
        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(d["nodes"]["B"]["dependencies"], ["A"])
        self.assertEqual(d["nodes"]["B"]["conditions"], {"key": "val"})
        
        # 文件读写 (JSON & YAML)
        fd_json, temp_path_json = tempfile.mkstemp(suffix=".json")
        fd_yaml, temp_path_yaml = tempfile.mkstemp(suffix=".yaml")
        os.close(fd_json)
        os.close(fd_yaml)
        
        try:
            # 保存 JSON 并加载
            dag.save_to_file(temp_path_json)
            loaded_dag_json = TaskDAG.load_from_file(temp_path_json)
            self.assertEqual(loaded_dag_json.graph_id, "dag_serial_test")
            self.assertEqual(loaded_dag_json.nodes["B"].conditions, {"key": "val"})
            self.assertEqual(loaded_dag_json.nodes["A"].status, NodeStatus.COMPLETED)
            
            # 保存 YAML 并加载
            dag.save_to_file(temp_path_yaml)
            loaded_dag_yaml = TaskDAG.load_from_file(temp_path_yaml)
            self.assertEqual(loaded_dag_yaml.graph_id, "dag_serial_test")
            self.assertEqual(loaded_dag_yaml.nodes["B"].conditions, {"key": "val"})
            self.assertEqual(loaded_dag_yaml.nodes["A"].status, NodeStatus.COMPLETED)
        finally:
            if os.path.exists(temp_path_json):
                os.remove(temp_path_json)
            if os.path.exists(temp_path_yaml):
                os.remove(temp_path_yaml)


if __name__ == "__main__":
    unittest.main()

