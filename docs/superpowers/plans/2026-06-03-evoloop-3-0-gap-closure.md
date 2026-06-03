# Evoloop 3.0 Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-impact gaps that prevent the repo from behaving like an actual Evoloop 3.0 control plane instead of a Phase 1 legacy-only shell.

**Architecture:** Keep the existing Phase 1 `TaskService` + `WorkflowEngine` as the transition runtime, but make native 3.0 playbooks reachable from the default registry and capable of producing native artifacts. Tighten adapter and serialization layers so HTTP, CLI, and MCP all expose the same 3.0 semantics instead of silently falling back to legacy behavior.

**Tech Stack:** Python, FastAPI, dataclasses, unittest, Vite frontend

---

## File Map

- `app/workflows/definitions.py`
  Responsibility: default task-definition registry used by HTTP and service bootstrap.
- `app/api/server.py`
  Responsibility: default task service bootstrap and frontend request normalization.
- `app/workflows/engine.py`
  Responsibility: shared transition runtime that executes legacy and native task definitions.
- `app/workflows/spec_to_agent.py`
  Responsibility: native 3.0 spec compilation playbook contract.
- `app/workflows/acceptance_review.py`
  Responsibility: native 3.0 acceptance review playbook contract and review helpers.
- `app/services/task_service.py`
  Responsibility: 3.0 facade mapping from transition runtime state into `WorkItem`, `ProductContext`, and `ArtifactGraph`.
- `app/mcp/tools.py`
  Responsibility: MCP adapter surface for external AI workers.
- `app/services/playbook_service.py`
  Responsibility: future native playbook runtime service; currently should be either aligned to frozen contracts or explicitly marked non-runtime.
- `tests/test_backend_phase1.py`
  Responsibility: API/service/runtime regression coverage.
- `tests/test_spec_to_agent.py`
  Responsibility: native `spec_to_agent` runtime/output coverage.
- `tests/test_acceptance_review.py`
  Responsibility: native `acceptance_review` runtime/output coverage.

### Task 1: Register Native 3.0 Playbooks In The Default Surface

**Files:**
- Modify: `app/workflows/definitions.py`
- Modify: `app/api/server.py`
- Test: `tests/test_backend_phase1.py`

- [ ] **Step 1: Write the failing tests for default registry and default service**

```python
def test_default_registry_exposes_native_3_0_playbooks(self):
    registry = build_task_registry()
    self.assertIn("spec_to_agent", registry)
    self.assertIn("acceptance_review", registry)

def test_default_task_service_can_create_native_tasks(self):
    service = build_default_task_service(root=Path(tempfile.mkdtemp()))
    spec_task = service.create_task(
        "spec_to_agent",
        {"username": "alice", "business_intent": "编译登录需求"},
    )
    self.assertEqual(spec_task.definition.type, "spec_to_agent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_backend_phase1.BackendPhase1Tests -v`
Expected: FAIL because `spec_to_agent` and `acceptance_review` are missing from the default registry.

- [ ] **Step 3: Register native playbooks in the default registry**

```python
from app.workflows.acceptance_review import build_acceptance_review_definition
from app.workflows.spec_to_agent import build_spec_to_agent_definition

def build_task_registry() -> dict[str, TaskDefinition]:
    legacy_manual = build_manual_definition(public_task_type="legacy_manual")
    legacy_prd = build_prd_definition(public_task_type="legacy_prd")
    spec_to_agent = build_spec_to_agent_definition()
    acceptance_review = build_acceptance_review_definition()
    return {
        "legacy_manual": legacy_manual,
        "manual": legacy_manual,
        "legacy_prd": legacy_prd,
        "prd": legacy_prd,
        "spec_to_agent": spec_to_agent,
        "acceptance_review": acceptance_review,
    }
```

- [ ] **Step 4: Extend frontend payload normalization so native tasks are reachable**

```python
if task_type == "spec_to_agent":
    normalized["business_intent"] = (
        payload.get("business_intent")
        or payload.get("prompt")
        or payload.get("goal")
        or payload.get("business_goal")
        or ""
    )
elif task_type == "acceptance_review":
    normalized["machine_spec"] = payload.get("machine_spec") or ""
    normalized["acceptance_protocol"] = payload.get("acceptance_protocol") or ""
    normalized["implementation_summary"] = payload.get("implementation_summary") or ""
    normalized["diff"] = payload.get("diff") or ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_backend_phase1.BackendPhase1Tests -v`
Expected: PASS for the new registry/service coverage.

- [ ] **Step 6: Commit**

```bash
git add app/workflows/definitions.py app/api/server.py tests/test_backend_phase1.py
git commit -m "feat: expose native 3.0 playbooks in default registry"
```

### Task 2: Make The Shared Runtime Produce Real Native 3.0 Artifacts

**Files:**
- Modify: `app/workflows/engine.py`
- Modify: `app/workflows/spec_to_agent.py`
- Modify: `app/workflows/acceptance_review.py`
- Test: `tests/test_spec_to_agent.py`
- Test: `tests/test_acceptance_review.py`

- [ ] **Step 1: Write failing runtime tests for native artifact names**

```python
def test_spec_to_agent_runtime_writes_expected_artifacts(self):
    service = build_cli_task_service(self.temp_dir, fake=True)
    task = service.create_task(
        "spec_to_agent",
        {"username": "alice", "business_intent": "做一个登录功能"},
    )
    service.run_task(task.task_id)
    names = [artifact.name for artifact in service.storage.list_artifacts(task.task_id)]
    self.assertEqual(
        names,
        [
            "machine_spec.yaml",
            "human_brief.md",
            "agent_package_codex.md",
            "acceptance.md",
            "review_checklist.md",
            "traceability.json",
        ],
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_spec_to_agent tests.test_acceptance_review -v`
Expected: FAIL because the runtime currently writes only `模块概览.md`.

- [ ] **Step 3: Add native artifact routing in the workflow engine**

```python
native_artifact_outputs = {
    "writer_machine_spec": ("machine_spec.yaml", self._render_machine_spec(task)),
    "writer_human_brief": ("human_brief.md", self._render_human_brief(task)),
    "writer_agent_package": ("agent_package_codex.md", self._render_agent_package(task)),
    "writer_acceptance": ("acceptance.md", self._render_acceptance(task)),
    "writer_review_checklist": ("review_checklist.md", self._render_review_checklist(task)),
    "writer_traceability": ("traceability.json", self._render_traceability(task)),
    "writer_review_result": ("review_result.md", self._render_review_result(task)),
}
```

- [ ] **Step 4: Rename the acceptance-review artifact step so the runtime can target it clearly**

```python
WorkflowStep(
    id="writer_review_result",
    type="artifact",
    title="写入 review_result.md 并校验图关系",
    role="Writer",
    allowed_tools=["artifact.write"],
)
```

- [ ] **Step 5: Keep legacy rendering logic untouched for `prd/manual`, and add focused native render helpers**

```python
def _render_machine_spec(self, task: Task) -> str:
    return yaml.safe_dump(
        {
            "title": task.context.title,
            "objective": task.context.goal,
            "requirements": [
                {"requirement_id": "req_primary", "statement": task.context.goal}
            ],
        },
        allow_unicode=True,
        sort_keys=False,
    )
```

- [ ] **Step 6: Run the native workflow tests again**

Run: `python3 -m unittest tests.test_spec_to_agent tests.test_acceptance_review -v`
Expected: PASS with native artifact names and native file content.

- [ ] **Step 7: Commit**

```bash
git add app/workflows/engine.py app/workflows/acceptance_review.py tests/test_spec_to_agent.py tests/test_acceptance_review.py
git commit -m "feat: generate native 3.0 workflow artifacts"
```

### Task 3: Make 3.0 Facades And MCP Serialization Honest

**Files:**
- Modify: `app/services/task_service.py`
- Modify: `app/mcp/tools.py`
- Test: `tests/test_backend_phase1.py`

- [ ] **Step 1: Write the failing tests for ProductContext serialization and native graph typing**

```python
def test_mcp_project_context_uses_to_dict_serialization(self):
    service, _, _ = self.make_service()
    task = service.create_task(
        "prd",
        {"username": "alice", "feature": "登录", "business_goal": "提升转化"},
    )
    ctx = service.get_product_context(task.task_id)
    self.assertEqual(ctx.requirements[0].to_dict()["requirement_id"], "req_primary")

def test_native_artifact_graph_uses_native_node_types(self):
    service = build_cli_task_service(self.temp_dir, fake=True)
    task = service.create_task(
        "spec_to_agent",
        {"username": "alice", "business_intent": "做一个登录功能"},
    )
    service.run_task(task.task_id)
    graph = service.get_artifact_graph(task.task_id)
    self.assertEqual(graph.source_of_truth_node().artifact_ref.name, "machine_spec")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_backend_phase1.BackendPhase1Tests -v`
Expected: FAIL or expose wrong graph typing / broken MCP serialization assumptions.

- [ ] **Step 3: Fix MCP dataclass serialization**

```python
return json.dumps(
    {
        "objective": ctx.objective,
        "requirements": [r.to_dict() for r in ctx.requirements],
        "decisions": [d.to_dict() for d in ctx.user_decisions],
    },
    ensure_ascii=False,
    indent=2,
)
```

- [ ] **Step 4: Teach `TaskService.get_artifact_graph()` about native 3.0 artifacts**

```python
native_type_map = {
    "machine_spec.yaml": ArtifactNodeType.MACHINE_SPEC,
    "human_brief.md": ArtifactNodeType.HUMAN_BRIEF,
    "agent_package_codex.md": ArtifactNodeType.AGENT_PACKAGE,
    "acceptance.md": ArtifactNodeType.ACCEPTANCE_PROTOCOL,
    "review_checklist.md": ArtifactNodeType.REVIEW_CHECKLIST,
    "review_result.md": ArtifactNodeType.REVIEW_RESULT,
    "traceability.json": ArtifactNodeType.TRACEABILITY_MAP,
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_backend_phase1.BackendPhase1Tests -v`
Expected: PASS, and manual invocation of MCP helpers returns JSON instead of an error string.

- [ ] **Step 6: Commit**

```bash
git add app/services/task_service.py app/mcp/tools.py tests/test_backend_phase1.py
git commit -m "fix: align 3.0 facades and MCP serialization"
```

### Task 4: Resolve The Broken Native Runtime Placeholder

**Files:**
- Modify: `app/services/playbook_service.py`
- Test: `tests/test_contracts_lane.py`

- [ ] **Step 1: Write a failing contract-alignment test**

```python
def test_playbook_service_uses_frozen_contract_field_names(self):
    item = WorkItem(
        work_type=WorkType.SPEC_TO_AGENT,
        playbook_id="pb",
        title="t",
        objective="o",
        workspace_id="w",
        product_context_ref="ctx",
        artifact_graph_ref="graph",
    )
    playbook = Playbook(playbook_id="pb", version="1", trigger_types=["intent"], steps=[])
    service = PlaybookService()
    service.start_playbook(item, playbook)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_contracts_lane -v`
Expected: FAIL with `AttributeError` for `step_graph` or `context_ref`.

- [ ] **Step 3: Either align the stub to the frozen contracts or explicitly downgrade it to a non-runtime placeholder**

```python
for step in playbook.steps:
    node = DAGNode(
        node_id=step.step_id,
        action_type="agent",
        dependencies=[],
    )

blackboard.write("input_context_ref", work_item.product_context_ref, owner_node="system")
```

- [ ] **Step 4: Add a defensive docstring if full runtime behavior is still intentionally incomplete**

```python
"""Transition stub.

This service only mirrors frozen-contract field names and must not be treated as
the production runtime until node execution is implemented.
"""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_contracts_lane -v`
Expected: PASS without contract-field mismatches.

- [ ] **Step 6: Commit**

```bash
git add app/services/playbook_service.py tests/test_contracts_lane.py
git commit -m "fix: align playbook service with frozen 3.0 contracts"
```

### Task 5: Run The Full Verification Sweep

**Files:**
- Modify: none
- Test: `tests/test_backend_phase1.py`
- Test: `tests/test_contracts_lane.py`
- Test: `tests/test_spec_to_agent.py`
- Test: `tests/test_acceptance_review.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Run backend unit coverage**

Run: `python3 -m unittest tests.test_backend_phase1 tests.test_contracts_lane tests.test_spec_to_agent tests.test_acceptance_review tests.test_cli_commands -v`
Expected: PASS

- [ ] **Step 2: Run compile-time verification**

Run: `python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py app/cli/*.py app/mcp/*.py`
Expected: no output

- [ ] **Step 3: Run frontend build to confirm API changes did not break the workspace**

Run: `npm --prefix frontend run build`
Expected: build succeeds; bundle-size warnings are acceptable if unchanged.

- [ ] **Step 4: Commit verification-only follow-up if needed**

```bash
git add .
git commit -m "test: verify 3.0 gap-closure changes"
```

## Self-Review

- Spec coverage:
  This plan covers the four concrete blockers found in review: native playbooks not registered by default, native workflows producing legacy artifacts, MCP/facade serialization mismatches, and the broken `PlaybookService` stub. It does not attempt full DAG runtime replacement, worker dispatch automation, or long-term memory design, which matches the “minimal closure” goal.
- Placeholder scan:
  No `TODO`, `TBD`, or “handle appropriately” placeholders were intentionally left in the task steps.
- Type consistency:
  The plan uses `playbook.steps`, `step.step_id`, `product_context_ref`, `machine_spec.yaml`, `review_result.md`, and `to_dict()` consistently with the current frozen-contract modules.
