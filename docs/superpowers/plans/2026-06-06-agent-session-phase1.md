# Evoloop 3.1 AgentSession Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first real bounded AgentSession runtime and migrate `machine_spec_compiler` so it runs through a session instead of direct one-shot executor control.

**Architecture:** Keep `WorkflowEngine` as deterministic outer Playbook control. Add `app/core/session.py` for session state contracts and `app/services/agent_runtime/` for bounded LLM/schema execution. `MachineSpecCompilerExecutor` becomes a thin adapter that builds an `AgentSession`, delegates to `AgentRuntime`, and converts the runtime result back to `StepResult`.

**Tech Stack:** Python dataclasses, unittest, existing `LLMPort.invoke`, existing `StepResult` / `StepStatus` / `DomainError`.

---

### Task 1: Core Session Contracts

**Files:**
- Create: `app/core/session.py`
- Test: `tests/test_agent_session_runtime.py`

- [ ] Write tests for `AgentSession` default IDs, max iteration guard fields, trace append behavior, and `AgentRunResult` success/block helpers.
- [ ] Run `python3 -m unittest tests.test_agent_session_runtime.AgentSessionContractTests -v` and confirm import fails.
- [ ] Create `app/core/session.py` with `AgentSession`, `AgentSessionState`, `AgentTurn`, `AgentObservation`, `AgentRunResult`.
- [ ] Run the contract tests and confirm they pass.

### Task 2: Minimal Bounded Runtime

**Files:**
- Create: `app/services/agent_runtime/__init__.py`
- Create: `app/services/agent_runtime/runtime.py`
- Test: `tests/test_agent_session_runtime.py`

- [ ] Add tests where runtime succeeds on valid JSON and records a session turn.
- [ ] Add tests where invalid JSON after retries returns blocked/degraded instead of fallback success.
- [ ] Implement `AgentRuntime.run_json_session()` using existing `llm.invoke` and strict JSON extraction.
- [ ] Run runtime tests and confirm they pass.

### Task 3: Machine Spec Compiler Migration

**Files:**
- Modify: `app/workflows/spec_to_agent.py`
- Test: `tests/test_spec_to_agent.py`

- [ ] Add/adjust tests asserting `machine_spec_compiler` outputs `agent_session_id` and `agent_session_trace` on success.
- [ ] Refactor `MachineSpecCompilerExecutor` to instantiate `AgentSession` and call `AgentRuntime.run_json_session()`.
- [ ] Preserve existing output schema and blocked behavior.
- [ ] Run `python3 -m unittest tests.test_spec_to_agent -v`.

### Task 4: Docs Update

**Files:**
- Modify: `docs/evoloop-3.1/architecture/00-global-architecture.md`
- Modify: `docs/evoloop-3.1/technical/00-agent-session-evolution.md`
- Modify: `AGENT_MAP.md`

- [ ] Document the newly added runtime files as first real 3.1 AgentSession implementation.
- [ ] Clarify only `machine_spec_compiler` is migrated in phase 1; `open_question_identifier` remains next.

### Task 5: Verification

**Files:**
- No source edits expected.

- [ ] Run `python3 -m unittest tests.test_agent_session_runtime tests.test_spec_to_agent tests.test_acceptance_review tests.test_cli_commands -v`.
- [ ] Run `python3 -m unittest tests.test_backend_phase1 -v`.
- [ ] Run `python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py`.
