# Evoloop 3.1 No Fake Success Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent production workflows and CLI review from turning LLM/parser failures into successful fake artifacts or PASS verdicts.

**Architecture:** Keep Playbook as the deterministic outer control plane, but make fallback/degraded states explicit at executor boundaries. Test fakes may remain, but production executors must return `blocked`, `changes_required`, or explicit `degraded` metadata instead of silent success.

**Tech Stack:** Python unittest, existing `TaskService`, `WorkflowEngine`, `StepResult`, `ReviewVerdict`, and 3.1 Markdown docs.

---

### Task 1: Lock Spec Compiler Degradation Behavior

**Files:**
- Modify: `tests/test_spec_to_agent.py`
- Modify: `app/workflows/spec_to_agent.py`
- Modify: `app/services/fakes.py`

- [ ] Add a failing test where a non-JSON LLM response makes `MachineSpecCompilerExecutor` return `StepStatus.BLOCKED` with `workflow.llm_degraded_fallback`.
- [ ] Run `python3 -m unittest tests.test_spec_to_agent.TestSpecToAgentExecutors -v` and confirm the new test fails because fallback still succeeds.
- [ ] Mark fallback data from `_invoke_llm_with_retry` with `degraded=true` and `fallback_reason`.
- [ ] Make `MachineSpecCompilerExecutor` block when fallback/degraded data reaches a source-of-truth compiler step.
- [ ] Update `FakeLLM` to return valid JSON for known compiler prompts so normal unit tests still exercise happy paths without relying on fallback.
- [ ] Run the spec-to-agent tests and confirm they pass.

### Task 2: Lock Acceptance Review Degradation Behavior

**Files:**
- Modify: `tests/test_acceptance_review.py`
- Modify: `app/workflows/acceptance_review.py`
- Modify: `app/services/fakes.py`

- [ ] Add a failing test where requirement coverage cannot parse reviewer JSON and no longer defaults every requirement to covered.
- [ ] Add a failing test where diff semantic review degradation creates a visible issue/fix task instead of empty issues.
- [ ] Run `python3 -m unittest tests.test_acceptance_review.TestAcceptanceReviewWorkflow -v` and confirm new tests fail under current fallback behavior.
- [ ] Change coverage fallback to `covered=false` with degraded metadata.
- [ ] Change diff semantic fallback to create a visible review-degraded issue and fix task.
- [ ] Ensure review result compiler returns `blocked` when degradation issues are present.
- [ ] Run acceptance review tests and confirm they pass.

### Task 3: Replace CLI Review Fake PASS in Non-Fake Mode

**Files:**
- Modify: `tests/test_cli_commands.py`
- Modify: `app/cli/commands.py`

- [ ] Add a failing test proving `review_cmd(..., fake=False)` does not produce an unconditional PASS for incomplete/TODO delivery.
- [ ] Route non-fake CLI review through the existing `acceptance_review` workflow using real service dependencies.
- [ ] Keep the old fixed report only under `fake=True`.
- [ ] Run CLI tests and confirm fake mode remains stable.

### Task 4: Document 3.1 Mock/Fallback Rules

**Files:**
- Modify: `docs/evoloop-3.1/architecture/00-global-architecture.md`
- Modify: `docs/evoloop-3.1/technical/00-agent-session-evolution.md`

- [ ] Add architecture rule: production control plane may degrade, block, or request human decision, but must not fake success.
- [ ] Add technical cleanup table for allowed test fakes, forbidden production fakes, and staged real replacements.
- [ ] Scan docs for `TBD` and unresolved placeholders.

### Task 5: Verify

**Files:**
- No source edits expected.

- [ ] Run `python3 -m unittest tests.test_spec_to_agent tests.test_acceptance_review tests.test_cli_commands -v`.
- [ ] Run `python3 -m unittest tests.test_backend_phase1 -v`.
- [ ] Run `python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py`.
- [ ] Report exact changed files, behavior changes, and residual mock/fake items.
