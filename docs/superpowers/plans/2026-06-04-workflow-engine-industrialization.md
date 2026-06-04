# Workflow Engine Industrialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Evoloop's workflow engine layer into a DAG-ready, checkpoint-aware, renderer-decoupled runtime while preserving current behavior.

**Architecture:** Keep `WorkflowEngine` as a compatibility facade. Add `WorkflowRuntimePlan` for plan validation/grouping/routing, `CheckpointManager` for transaction checkpoint semantics, and `ContextCompilerService` for artifact rendering. Existing playbooks continue using `TaskDefinition` and `WorkflowSpec`.

**Tech Stack:** Python dataclasses, unittest, existing `TaskDefinition`/`Task`/`StepResult` models, existing `FakeStorage` and tool service fakes.

---

### Task 1: Runtime Planning Tests

**Files:**
- Create: `tests/test_workflow_runtime.py`
- Create: `app/workflows/runtime.py`

- [ ] **Step 1: Write failing tests**

```python
import tempfile
import unittest
from pathlib import Path

from app.core.errors import DomainError
from app.core.task import StepResult, StepStatus, WorkflowSpec, WorkflowStep
from app.workflows.runtime import WorkflowRuntimePlan


class WorkflowRuntimePlanTests(unittest.TestCase):
    def test_rejects_duplicate_step_ids(self):
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[
                WorkflowStep(id="same", type="context", title="A"),
                WorkflowStep(id="same", type="agent", title="B"),
            ],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual(raised.exception.code, "workflow.duplicate_step_id")

    def test_rejects_dangling_routes(self):
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[WorkflowStep(id="a", type="context", title="A", on_success="missing")],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual(raised.exception.code, "workflow.dangling_route")

    def test_groups_contiguous_parallel_steps(self):
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="context", title="A"),
                WorkflowStep(id="b", type="agent", title="B", parallel_group="reviewers"),
                WorkflowStep(id="c", type="agent", title="C", parallel_group="reviewers"),
                WorkflowStep(id="d", type="gate", title="D"),
            ],
        )

        plan = WorkflowRuntimePlan.from_workflow(workflow)

        self.assertEqual([[step.id for step in batch.steps] for batch in plan.batches_from("a")], [["a"], ["b", "c"], ["d"]])

    def test_result_next_step_overrides_step_success_route(self):
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="gate", title="A", on_success="b"),
                WorkflowStep(id="b", type="agent", title="B"),
                WorkflowStep(id="c", type="agent", title="C"),
            ],
        )
        plan = WorkflowRuntimePlan.from_workflow(workflow)
        result = StepResult("a", StepStatus.SUCCEEDED, next_step_id="c")

        self.assertEqual(plan.resolve_success_route("a", result), "c")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_workflow_runtime.WorkflowRuntimePlanTests -v`
Expected: FAIL or import error for missing `app.workflows.runtime`.

- [ ] **Step 3: Implement minimal runtime plan**

Create `WorkflowRuntimePlan`, `WorkflowExecutionBatch`, validation, `batches_from`, and route helpers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_workflow_runtime.WorkflowRuntimePlanTests -v`
Expected: PASS.

### Task 2: Checkpoint Manager Tests

**Files:**
- Modify: `tests/test_workflow_runtime.py`
- Create: `app/workflows/checkpoints.py`

- [ ] **Step 1: Write failing tests**

```python
from app.core.task import TaskStatus
from app.workflows.checkpoints import CheckpointManager


class WorkflowCheckpointManagerTests(unittest.TestCase):
    def test_resume_uses_checkpoint_next_step_when_not_waiting_for_user(self):
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": "running"}

        self.assertEqual(manager.resume_step_id(checkpoint), "writer")

    def test_resume_ignores_waiting_user_checkpoint(self):
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": TaskStatus.WAITING_FOR_USER.value}

        self.assertIsNone(manager.resume_step_id(checkpoint))

    def test_build_transaction_checkpoint_payload(self):
        manager = CheckpointManager(storage=None)
        payload = manager.build_payload(
            task_id="task_1",
            run_id="run_1",
            last_completed_step_id="a",
            next_step_id="b",
            status="running",
            attempt=2,
            completed_step_ids=["a"],
        )

        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["completed_step_ids"], ["a"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_workflow_runtime.WorkflowCheckpointManagerTests -v`
Expected: FAIL or import error.

- [ ] **Step 3: Implement minimal checkpoint manager**

Add `resume_step_id`, `build_payload`, and storage-compatible `save_success_checkpoint`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_workflow_runtime.WorkflowCheckpointManagerTests -v`
Expected: PASS.

### Task 3: Context Compiler Tests

**Files:**
- Modify: `tests/test_workflow_runtime.py`
- Create: `app/workflows/context_compiler.py`

- [ ] **Step 1: Write failing tests**

```python
from app.core.context import TaskContext
from app.core.task import Task, TaskDefinition
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.spec_to_agent import build_spec_to_agent_definition


class ContextCompilerServiceTests(unittest.TestCase):
    def make_native_task(self):
        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_1",
            task_type="spec_to_agent",
            username="alice",
            goal="Compile login requirements",
            title="Login",
            inputs={"business_intent": "Users must log in safely"},
        )
        return Task(definition=definition, context=context, task_id="task_1")

    def test_renders_native_machine_spec_payload(self):
        task = self.make_native_task()
        step = task.definition.workflow.steps[5]
        compiler = ContextCompilerService()

        name, content = compiler.artifact_payload(task, step)

        self.assertEqual(name, "machine_spec.yaml")
        self.assertIn("source of truth", content.lower())
        self.assertIn("Users must log in safely", content)

    def test_rejects_native_artifact_without_single_output_key(self):
        task = self.make_native_task()
        bad_step = WorkflowStep(id="bad", type="artifact", title="Bad", output_keys=[])
        compiler = ContextCompilerService()

        with self.assertRaises(DomainError) as raised:
            compiler.artifact_payload(task, bad_step)

        self.assertEqual(raised.exception.code, "workflow.native_artifact_contract_invalid")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_workflow_runtime.ContextCompilerServiceTests -v`
Expected: FAIL or import error.

- [ ] **Step 3: Move render logic into compiler**

Move existing render methods from `WorkflowEngine` to `ContextCompilerService` and expose `artifact_payload(task, step)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_workflow_runtime.ContextCompilerServiceTests -v`
Expected: PASS.

### Task 4: Engine Integration

**Files:**
- Modify: `app/workflows/engine.py`
- Modify: `tests/test_backend_phase1.py` only if an existing assertion needs compatibility update; prefer no changes.

- [ ] **Step 1: Wire runtime plan into `WorkflowEngine.run`**

Use `WorkflowRuntimePlan.from_workflow(task.definition.workflow)` for validation, start selection, batches, and success route decisions.

- [ ] **Step 2: Wire checkpoint manager**

Use `CheckpointManager.resume_step_id` inside `_start_index` and `save_success_checkpoint` for successful steps.

- [ ] **Step 3: Wire context compiler**

Replace `_native_artifact_payload`, `_render_prd`, and `_render_manual` calls with `self.context_compiler.artifact_payload(task, step)`.

- [ ] **Step 4: Run runtime and legacy tests**

Run: `python3 -m unittest tests.test_workflow_runtime tests.test_backend_phase1 tests.test_spec_to_agent tests.test_acceptance_review -v`
Expected: PASS.

### Task 5: Verification

**Files:**
- Verify only.

- [ ] **Step 1: Compile backend modules**

Run: `python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py`
Expected: no output and exit 0.

- [ ] **Step 2: Inspect git diff**

Run: `git diff -- app/workflows tests docs/superpowers`
Expected: only planned runtime/compiler/checkpoint/test/spec/plan changes.
