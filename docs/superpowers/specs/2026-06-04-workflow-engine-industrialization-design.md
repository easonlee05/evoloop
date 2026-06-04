# Workflow Engine Industrialization Design

## Goal

Bring the Evoloop 3.0 workflow engine layer to an industrial-grade transition point without breaking the existing `TaskService`, API, CLI, legacy manual/PRD playbooks, or native 3.0 playbooks.

## Context

`docs/evoloop-3.0/technical/03-engineering-evolution.md` identifies the workflow layer gap as:

- replace linear scheduling with DAG-ready runtime behavior;
- add transaction-grade checkpoint and replay semantics;
- keep engine responsibility pure by moving render/string assembly out of `WorkflowEngine`.

The current `app/workflows/engine.py` mixes scheduling, state transitions, LLM calls, arbitration, artifact rendering, native artifact rendering, event emission, and checkpoint writes. This makes the engine hard to test and hard to evolve into `PlaybookDAGRuntime`.

## Approach

Use a compatibility-first split:

1. Keep `WorkflowEngine.run/apply_decision/cancel` as the stable facade.
2. Add focused workflow runtime modules that can be tested independently.
3. Move artifact/context rendering into `ContextCompilerService`.
4. Preserve all existing public behavior while adding DAG-ready primitives.

This is a mid-term industrialization step, not a full distributed runtime. It prepares the codebase for `PlaybookDAGRuntime` while avoiding a high-risk rewrite.

## Components

### `app/workflows/runtime.py`

Responsibilities:

- compile existing `WorkflowSpec.steps` into an executable plan;
- validate duplicate step IDs, dangling routes, and parallel group shape;
- group ready nodes from linear steps and contiguous `parallel_group` steps;
- centralize route decisions from `StepResult.next_step_id`, `WorkflowStep.on_success`, and `WorkflowStep.on_failure`.

This module does not invoke LLMs, tools, or storage. It only owns runtime planning and route selection.

### `app/workflows/checkpoints.py`

Responsibilities:

- create transaction checkpoint payloads;
- standardize `run_id`, `attempt`, `last_completed_step_id`, `next_step_id`, `status`, and completed-step tracking;
- read existing legacy checkpoints safely;
- provide replay start selection from checkpoint state.

It remains compatible with `FakeStorage.save_checkpoint(task, last_completed_step_id, next_step_id)` by writing richer metadata through optional storage methods only when available.

### `app/workflows/context_compiler.py`

Responsibilities:

- render legacy PRD and manual artifacts;
- render native 3.0 artifacts: `machine_spec`, `human_brief`, `agent_package`, `acceptance`, `review_checklist`, `traceability`, `review_result`;
- validate native artifact contracts;
- keep `WorkflowEngine` focused on state transitions.

### `app/workflows/engine.py`

Responsibilities after refactor:

- task/run lifecycle;
- step execution dispatch;
- result handling and task status transitions;
- invoking `ContextCompilerService` for artifact payloads;
- invoking `WorkflowRuntimePlan` for execution grouping and routing;
- invoking `CheckpointManager` for checkpoint decisions.

## Data Flow

```text
TaskService.run_task
  -> WorkflowEngine.run
  -> WorkflowRuntimePlan.from_workflow(definition.workflow)
  -> grouped execution batches
  -> WorkflowEngine._run_step
  -> StepResult
  -> WorkflowRuntimePlan.resolve_success_route / resolve_failure_route
  -> CheckpointManager save/load compatibility layer
  -> storage events + context + artifacts
```

## Error Handling

- Invalid workflow plans fail fast with `DomainError` before execution.
- Unknown step types remain step failures, preserving current semantics.
- Failed parallel group node aborts the group and marks task failed.
- Denied artifact writes remain `BLOCKED`; other write errors remain `FAILED`.
- Legacy checkpoint files lacking new metadata remain readable.

## Testing

Add `tests/test_workflow_runtime.py` for isolated runtime/compiler/checkpoint behavior:

- duplicate step IDs are rejected;
- dangling route targets are rejected;
- linear steps and contiguous parallel groups compile into batches;
- route resolution honors explicit `StepResult.next_step_id` before step-level defaults;
- checkpoint manager resumes from `next_step_id` when the stored status is not `waiting_for_user`;
- context compiler renders native artifacts and rejects invalid native artifact contracts.

Run full backend validation:

```bash
python3 -m unittest tests.test_workflow_runtime tests.test_backend_phase1 tests.test_spec_to_agent tests.test_acceptance_review -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```
