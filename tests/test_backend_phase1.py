import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from fastapi.testclient import TestClient

from app.api.server import build_default_task_service, create_app
from app.core.artifact_graph import ArtifactNodeType
from app.core.ports import LLMResult
from app.core.task import TaskStatus
from app.core.tools import ToolCall
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.mcp.tools import register_tools


class BackendPhase1Tests(unittest.TestCase):
    def make_service(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        self.addCleanup(temp.cleanup)
        return service, storage, tool_service

    def test_default_registry_exposes_native_3_0_playbooks(self):
        registry = build_task_registry()

        self.assertIn("spec_to_agent", registry)
        self.assertIn("acceptance_review", registry)

    def test_default_task_service_can_create_native_tasks(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        service = build_default_task_service(root=Path(temp.name))

        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "编译登录需求",
            },
        )

        self.assertEqual(task.definition.type, "spec_to_agent")

    def test_create_task_api_accepts_spec_to_agent_business_intent(self):
        service, _, _ = self.make_service()
        client = TestClient(create_app(service))

        response = client.post(
            "/api/tasks",
            json={
                "type": "spec_to_agent",
                "username": "alice",
                "business_intent": "编译登录需求",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = service.get_task(response.json()["task_id"])
        self.assertEqual(task.definition.type, "spec_to_agent")
        self.assertEqual(task.context.inputs["business_intent"], "编译登录需求")

    def test_create_task_api_accepts_acceptance_review_payload(self):
        service, _, _ = self.make_service()
        client = TestClient(create_app(service))

        response = client.post(
            "/api/tasks",
            json={
                "type": "acceptance_review",
                "username": "alice",
                "machine_spec": "req_login: 用户必须能登录",
                "acceptance_protocol": "case_login: 校验登录成功",
                "implementation_summary": "已完成登录接口与前端流程",
                "diff": "+ add login handler",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = service.get_task(response.json()["task_id"])
        self.assertEqual(task.definition.type, "acceptance_review")
        self.assertEqual(task.context.inputs["machine_spec"], "req_login: 用户必须能登录")
        self.assertEqual(task.context.inputs["acceptance_protocol"], "case_login: 校验登录成功")
        self.assertEqual(task.context.inputs["implementation_summary"], "已完成登录接口与前端流程")
        self.assertEqual(task.context.inputs["diff"], "+ add login handler")

    def test_default_app_wiring_accepts_native_spec_to_agent_post(self):
        class FakeDefaultLLM(FakeLLM):
            def __init__(self, api_key="", base_url=""):
                self.api_key = api_key
                self.base_url = base_url

        class FakeDefaultKnowledge(FakeKnowledge):
            def __init__(self, repo_path, timeout_seconds=5):
                self.repo_path = repo_path
                self.timeout_seconds = timeout_seconds

        with patch("app.api.server.OpenAILLM", FakeDefaultLLM), patch("app.api.server.GBrainKnowledge", FakeDefaultKnowledge):
            client = TestClient(create_app())
            response = client.post(
                "/api/tasks",
                json={
                    "type": "spec_to_agent",
                    "username": "alice",
                    "business_intent": "编译登录需求",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("task_id", payload)
        self.assertEqual(payload["status"], "created")

    def test_product_context_and_mcp_context_serialize_native_requirements(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        context = service.get_product_context(task.task_id)
        self.assertEqual(context.requirements[0].statement, "将登录需求编译成 agent 可执行任务包")

        class DummyMCP:
            def __init__(self):
                self.funcs = {}

            def tool(self):
                def decorator(fn):
                    self.funcs[fn.__name__] = fn
                    return fn
                return decorator

        dummy = DummyMCP()
        register_tools(dummy)
        with patch("app.mcp.tools.get_service", return_value=service):
            payload = json.loads(dummy.funcs["get_project_context"](task.task_id))

        self.assertEqual(payload["requirements"][0]["statement"], "将登录需求编译成 agent 可执行任务包")

    def test_native_artifact_graph_uses_native_node_types(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        service.run_task(task.task_id)

        graph = service.get_artifact_graph(task.task_id)
        node_types_by_name = {node.artifact_ref.name: node.type for node in graph.nodes}

        self.assertEqual(node_types_by_name["machine_spec.yaml"], ArtifactNodeType.MACHINE_SPEC)
        self.assertEqual(node_types_by_name["human_brief.md"], ArtifactNodeType.HUMAN_BRIEF)
        self.assertEqual(node_types_by_name["agent_package_codex.md"], ArtifactNodeType.AGENT_PACKAGE)
        self.assertEqual(node_types_by_name["acceptance.md"], ArtifactNodeType.ACCEPTANCE_PROTOCOL)
        self.assertEqual(node_types_by_name["review_checklist.md"], ArtifactNodeType.REVIEW_CHECKLIST)
        self.assertEqual(node_types_by_name["traceability.json"], ArtifactNodeType.TRACEABILITY_MAP)

    def test_work_items_api_lists_native_and_legacy_work(self):
        service, _, _ = self.make_service()
        native_task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        legacy_task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "积分防刷网关",
                "business_goal": "降低异常积分套利",
            },
        )

        client = TestClient(create_app(service))
        response = client.get("/api/work-items")

        self.assertEqual(response.status_code, 200)
        work_items = {item["work_id"]: item for item in response.json()["work_items"]}
        self.assertEqual(work_items[native_task.task_id]["work_type"], "spec_to_agent")
        self.assertEqual(work_items[legacy_task.task_id]["work_type"], "legacy_prd")

    def test_work_item_detail_api_returns_frozen_contract_payload(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_id"], task.task_id)
        self.assertEqual(payload["work_type"], "spec_to_agent")
        self.assertEqual(payload["product_context_ref"], f"ctx_{task.task_id}")

    def test_work_item_product_context_api_returns_native_requirement(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}/product-context")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requirements"][0]["statement"], "将登录需求编译成 agent 可执行任务包")

    def test_work_item_artifact_graph_api_returns_native_node_types(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )
        service.run_task(task.task_id)

        client = TestClient(create_app(service))
        response = client.get(f"/api/work-items/{task.task_id}/artifact-graph")

        self.assertEqual(response.status_code, 200)
        node_types_by_name = {
            node["artifact_ref"]["name"]: node["type"]
            for node in response.json()["nodes"]
        }
        self.assertEqual(node_types_by_name["machine_spec.yaml"], "machine_spec")
        self.assertEqual(node_types_by_name["agent_package_codex.md"], "agent_package")

    def test_workflow_step_status_flow_completes_prd(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "积分防刷网关",
                "business_goal": "降低异常积分套利",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        task_events = storage.read_events(task.task_id)
        event_types = [event.type for event in task_events]
        self.assertIn("workflow.step.started", event_types)
        self.assertIn("workflow.step.completed", event_types)
        self.assertIn("task.completed", event_types)

    def test_recent_conversations_returns_all_tasks_without_truncation(self):
        service, _, _ = self.make_service()
        for index in range(25):
            service.create_task(
                "prd",
                {
                    "username": "alice",
                    "feature": f"任务 {index}",
                    "business_goal": "验证最近对话列表不截断",
                },
            )

        client = TestClient(create_app(service))
        response = client.get('/api/conversations/recent')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        total = len(payload.get('today', [])) + len(payload.get('yesterday', [])) + len(payload.get('older', []))
        self.assertEqual(total, 25)

    def test_workflow_run_and_step_events_include_timing_metadata(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "性能诊断",
                "business_goal": "定位慢请求来源",
            },
        )

        service.run_task(task.task_id)

        events = [event.to_dict() for event in storage.read_events(task.task_id)]
        run_started = [event for event in events if event["type"] == "workflow.run.started"]
        run_completed = [event for event in events if event["type"] == "workflow.run.completed"]
        step_completed = [event for event in events if event["type"] == "workflow.step.completed"]

        self.assertEqual(len(run_started), 1)
        self.assertEqual(len(run_completed), 1)
        run_id = run_started[0]["payload"].get("run_id")
        self.assertTrue(run_id.startswith("run_"))
        self.assertEqual(run_completed[0]["payload"].get("run_id"), run_id)
        self.assertIsInstance(run_completed[0]["payload"].get("duration_ms"), int)
        self.assertGreaterEqual(run_completed[0]["payload"].get("duration_ms"), 0)
        self.assertTrue(step_completed)
        self.assertTrue(all(event["payload"].get("run_id") == run_id for event in step_completed))
        self.assertTrue(all(isinstance(event["payload"].get("duration_ms"), int) for event in step_completed))

    def test_llm_telemetry_events_are_recorded_without_sensitive_payloads(self):
        class TelemetryLLM:
            def invoke_stream(self, role, prompt, context, telemetry=None):
                if telemetry:
                    telemetry(
                        "llm.call.started",
                        {
                            "call_id": "llm_test_call",
                            "model": "diagnostic-model",
                            "base_url_host": "relay.example.test",
                            "prompt": "must not be stored",
                            "api_key": "secret-key",
                        },
                    )
                    telemetry("llm.call.headers_received", {"call_id": "llm_test_call", "ttfb_ms": 12})
                    telemetry("llm.call.first_token", {"call_id": "llm_test_call", "first_token_ms": 34})
                yield "hello"
                yield " world"
                if telemetry:
                    telemetry(
                        "llm.call.completed",
                        {
                            "call_id": "llm_test_call",
                            "duration_ms": 56,
                            "output_chars": 11,
                            "chunk_count": 2,
                        },
                    )

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=TelemetryLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "中转站诊断",
                "business_goal": "判断慢是否来自模型链路",
            },
        )

        service.run_task(task.task_id, until_step_id="pm_draft")

        events = [event.to_dict() for event in storage.read_events(task.task_id)]
        llm_events = [event for event in events if event["type"].startswith("llm.call.")]
        event_types = [event["type"] for event in llm_events]
        self.assertIn("llm.call.started", event_types)
        self.assertIn("llm.call.headers_received", event_types)
        self.assertIn("llm.call.first_token", event_types)
        self.assertIn("llm.call.completed", event_types)
        for event in llm_events:
            payload = event["payload"]
            self.assertEqual(payload.get("step_id"), "pm_draft")
            self.assertTrue(payload.get("run_id", "").startswith("run_"))
            self.assertNotIn("prompt", payload)
            self.assertNotIn("api_key", payload)

    def test_needs_arbitration_pauses_and_resumes(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "结算重试策略",
                "business_goal": "定义失败补偿",
                "force_arbitration": True,
            },
        )

        paused = service.run_task(task.task_id)
        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)
        self.assertEqual(paused.waiting_step_id, "arbitration_business_tradeoff")

        resumed = service.apply_decision(
            task.task_id,
            decision="选择方案 B，接受短时间缓存脏数据，但必须加入事后对账。",
            selected_option="B",
        )

        self.assertEqual(resumed.status, TaskStatus.COMPLETED)
        context = storage.load_context(task.task_id)
        self.assertEqual(context.user_decisions[0].selected_option, "B")
        event_types = [event.type for event in storage.read_events(task.task_id)]
        self.assertIn("arbitration.requested", event_types)
        self.assertIn("arbitration.applied", event_types)

    def test_apply_decision_persists_quoted_selections(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "引用片段决策",
                "business_goal": "保留前端选区来源",
                "force_arbitration": True,
            },
        )

        paused = service.run_task(task.task_id)
        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)

        quoted_selections = [
            {
                "source_type": "message",
                "source_id": "msg_1",
                "source_label": "PM Agent",
                "text": "需要保留这个引用来源",
            }
        ]
        resumed = service.apply_decision(
            task.task_id,
            decision="按引用内容继续修改",
            selected_option="A",
            quoted_selections=quoted_selections,
        )

        self.assertEqual(resumed.status, TaskStatus.COMPLETED)
        context = storage.load_context(task.task_id)
        self.assertEqual(context.user_decisions[0].quoted_selections, quoted_selections)
        applied_events = [event.to_dict() for event in storage.read_events(task.task_id) if event.type == "arbitration.applied"]
        self.assertEqual(applied_events[0]["payload"]["quoted_selections"], quoted_selections)

    def test_checkpoint_restore_continues_from_last_successful_step(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "灰度发布",
                "business_goal": "降低发布风险",
            },
        )
        service.run_task(task.task_id, until_step_id="pm_draft")
        checkpoint = storage.load_checkpoint(task.task_id)
        self.assertEqual(checkpoint["last_completed_step_id"], "pm_draft")

        registry = build_task_registry()
        restored_engine = WorkflowEngine(
            tool_service=ToolService.default(root=storage.root, knowledge=FakeKnowledge()),
            llm=FakeLLM(),
            storage=storage,
        )
        restored = TaskService(registry=registry, engine=restored_engine, storage=storage)
        result = restored.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        latest = storage.load_checkpoint(task.task_id)
        self.assertEqual(latest["last_completed_step_id"], "final_checkpoint")

    def test_tool_policy_allows_and_denies(self):
        service, _, tool_service = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "权限网关",
                "business_goal": "统一鉴权",
            },
        )
        allowed = tool_service.invoke(
            task.definition,
            task.context,
            ToolCall(
                task_id=task.task_id,
                step_id="retrieve_knowledge",
                agent_role="SYSTEM",
                tool_name="knowledge.retrieve",
                arguments={"query": "鉴权"},
            ),
        )
        denied = tool_service.invoke(
            task.definition,
            task.context,
            ToolCall(
                task_id=task.task_id,
                step_id="pm_draft",
                agent_role="PM",
                tool_name="artifact.write",
                arguments={"name": "PRD.md", "content": "# bad"},
            ),
        )

        self.assertEqual(allowed.status, "succeeded")
        self.assertEqual(denied.status, "denied")
        self.assertEqual(denied.error.code, "tool.denied")

    def test_artifact_write_is_idempotent_by_logical_name(self):
        service, storage, tool_service = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "账单中心",
                "business_goal": "生成账单 PRD",
            },
        )
        call = ToolCall(
            task_id=task.task_id,
            step_id="write_prd_artifact",
            agent_role="Writer",
            tool_name="artifact.write",
            arguments={"name": "PRD.md", "content": "# 账单中心\n"},
        )

        first = tool_service.invoke(task.definition, task.context, call)
        second = tool_service.invoke(task.definition, task.context, call)

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(first.artifacts[0].artifact_id, second.artifacts[0].artifact_id)
        self.assertEqual(first.artifacts[0].version, second.artifacts[0].version)
        self.assertEqual(len(storage.list_artifacts(task.task_id)), 1)

    def test_fake_llm_and_fake_tools_run_minimal_prd_workflow(self):
        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "bob",
                "feature": "工单升级",
                "business_goal": "提高客服响应效率",
                "constraints": ["首期只做企业版"],
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        self.assertEqual([artifact.name for artifact in artifacts], ["PRD.md"])
        prd = storage.read_artifact(artifacts[0].artifact_id)
        self.assertIn("工单升级", prd.content)
        self.assertIn("提高客服响应效率", prd.content)

    def test_prd_artifact_uses_product_requirement_structure_not_raw_prompt(self):
        service, storage, _ = self.make_service()
        raw_prompt = "请为电商平台设计一份完整 PRD，主题是「积分防刷网关」。背景：签到脚本、小号下单返积分、退款套利、邀请作弊致积分损失。"
        task = service.create_task(
            "prd",
            {
                "username": "frontend",
                "feature": "积分防刷网关",
                "business_goal": raw_prompt,
            },
        )

        service.run_task(task.task_id)

        artifacts = storage.list_artifacts(task.task_id)
        prd = storage.read_artifact(artifacts[0].artifact_id)
        required_sections = [
            "## 1. 背景与问题定义",
            "## 2. 业务目标与非目标",
            "## 3. 用户角色与使用场景",
            "## 4. 功能需求",
            "## 5. 风控策略与规则",
            "## 6. 数据与指标",
            "## 7. 异常流程与降级",
            "## 8. 验收标准",
        ]
        for section in required_sections:
            self.assertIn(section, prd.content)
        self.assertIn("签到脚本", prd.content)
        self.assertIn("小号下单返积分", prd.content)
        self.assertNotIn("请为电商平台设计一份完整 PRD", prd.content)

    def test_frontend_task_payload_exposes_knowledge_status(self):
        service, _, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "知识联调",
                "business_goal": "让前端能看到知识检索状态",
            },
        )

        service.run_task(task.task_id, until_step_id="retrieve_knowledge")
        payload = service.get_task(task.task_id)

        self.assertIn("knowledge", payload.context.degradation_state)
        self.assertIn("items", payload.context.degradation_state["knowledge"])

    def test_frontend_task_status_maps_knowledge_state(self):
        from app.api.server import _frontend_task

        service, storage, _ = self.make_service()
        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "知识状态",
                "business_goal": "让前端能区分错误和无结果",
            },
        )
        context = storage.load_context(task.task_id)
        context.degradation_state["knowledge"] = {"degraded": False, "items": 0, "preview": []}
        storage.save_context(context)
        task = storage.load_task(task.task_id, service.registry)

        payload = _frontend_task(task)

        self.assertEqual(payload["knowledge_status"]["state"], "no_results")

    def test_retrieve_knowledge_builds_richer_query_and_preview(self):
        captured = {}

        class CapturingKnowledge:
            def retrieve(self, query, scope=None):
                captured["query"] = query
                return {
                    "query": query,
                    "scope": scope or "default",
                    "degraded": False,
                    "items": [
                        {"title": "Agent Map", "summary": "仓库导航"},
                        {"title": "API Contract", "summary": "接口契约"},
                    ],
                }

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=CapturingKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)

        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "WorkflowEngine",
                "business_goal": "说明 ToolService 协作方式",
            },
        )

        service.run_task(task.task_id, until_step_id="retrieve_knowledge")
        state = storage.load_context(task.task_id).degradation_state["knowledge"]

        self.assertIn("WorkflowEngine", captured["query"])
        self.assertIn("ToolService", captured["query"])
        self.assertEqual(state["preview"][0]["title"], "Agent Map")

    def test_max_review_rounds_pause_for_arbitration_without_force_flag(self):
        class AlwaysFailReviewerLLM(FakeLLM):
            def invoke(self, role, prompt, context):
                if role == "Reviewer":
                    return LLMResult(content="FAIL", structured={"role": role})
                return super().invoke(role, prompt, context)

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        registry = build_task_registry()
        registry["prd"].round_policy["max_rounds"] = 1
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=AlwaysFailReviewerLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)

        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "支付对账",
                "business_goal": "让评审多轮失败后停下来等用户拍板",
            },
        )

        paused = service.run_task(task.task_id)

        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)
        self.assertEqual(paused.waiting_step_id, "arbitration_business_tradeoff")

    def test_malformed_reviewer_output_does_not_count_as_gate_pass(self):
        class MalformedReviewerLLM(FakeLLM):
            def invoke(self, role, prompt, context):
                if role == "Reviewer":
                    return LLMResult(content="Reviewer response: FAIL", structured={"role": role})
                return super().invoke(role, prompt, context)

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        registry = build_task_registry()
        registry["prd"].round_policy["max_rounds"] = 1
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=MalformedReviewerLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)

        task = service.create_task(
            "prd",
            {
                "username": "alice",
                "feature": "库存回写",
                "business_goal": "防止脏 Reviewer 输出把门禁误判为通过",
            },
        )

        paused = service.run_task(task.task_id)

        self.assertEqual(paused.status, TaskStatus.WAITING_FOR_USER)
        self.assertEqual(paused.waiting_step_id, "arbitration_business_tradeoff")


if __name__ == "__main__":
    unittest.main()
