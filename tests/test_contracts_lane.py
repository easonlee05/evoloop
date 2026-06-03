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


if __name__ == "__main__":
    unittest.main()
