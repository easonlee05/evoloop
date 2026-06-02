# LLM Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add diagnostic telemetry that explains whether slow agent runs are caused by orchestration, repeated runs, network/proxy latency, model first-token latency, or streaming throughput.

**Architecture:** WorkflowEngine emits run/step timing events and passes a per-run telemetry callback into the LLM client. OpenAILLM emits sanitized lifecycle events for request start, response headers, first token, completion, failure, and fallback without logging prompts, API keys, or full URLs.

**Tech Stack:** Python unittest, existing Event/FakeStorage/WorkflowEngine/OpenAILLM, standard library time/uuid/urllib.parse.

---

### Task 1: Workflow run and step telemetry

**Files:**
- Modify: `tests/test_backend_phase1.py`
- Modify: `app/workflows/engine.py`

- [ ] Write failing tests for `workflow.run.*`, `run_id`, and step `duration_ms`.
- [ ] Run targeted unittest and confirm failure.
- [ ] Implement run_id generation, run start/completed events, and duration fields.
- [ ] Run targeted unittest and confirm pass.

### Task 2: LLM diagnostic telemetry

**Files:**
- Modify: `tests/test_backend_phase1.py`
- Modify: `app/workflows/engine.py`
- Modify: `app/services/llm.py`

- [ ] Write failing tests for `llm.call.*` events using a fake telemetry LLM.
- [ ] Run targeted unittest and confirm failure.
- [ ] Add optional `telemetry` callback to `invoke_stream`, emit sanitized timing events, and wire engine callback.
- [ ] Run backend tests and py_compile.

### Task 3: Verify no Writer output cap

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_backend_phase1.py`

- [ ] Confirm no max_tokens or Writer word limit is added.
- [ ] Verify tests pass.
