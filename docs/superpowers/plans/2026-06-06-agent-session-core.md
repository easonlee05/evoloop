# AgentSession Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Evoloop 3.1 AgentSession into a real single-step runtime contract with agenda, richer runtime metadata, and explicit degraded outcomes.

**Architecture:** Preserve the existing workflow boundary and `run_json_session()` entrypoint while evolving `app/core/session.py` and `app/services/agent_runtime/runtime.py` into the real source of truth for session state, tool accounting, schema recovery, and auditable trace output.

**Tech Stack:** Python 3, unittest, dataclasses, existing Workflow/ToolService runtime

---

### Task 1: Lock the session contract with tests

**Files:**
- Modify: `tests/test_agent_session_runtime.py`
- Modify: `app/core/session.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_session_trace_includes_agenda_and_runtime_metadata(self):
    from app.core.session import AgentSession

    session = AgentSession(task_id="task_1", step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
    session.set_runtime_contract(["knowledge.retrieve"], ["primary_requirement"])
    session.add_agenda_item(title="Inspect ambiguity", rationale="Need a worklist", priority="high")
    trace = session.to_trace()

    self.assertEqual(trace["allowed_tools"], ["knowledge.retrieve"])
    self.assertEqual(trace["output_schema_keys"], ["primary_requirement"])
    self.assertEqual(trace["state"]["agenda_items"][0]["title"], "Inspect ambiguity")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_agent_session_runtime.AgentSessionContractTests.test_agent_session_trace_includes_agenda_and_runtime_metadata -v`
Expected: FAIL because the new contract helpers and trace fields do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class AgendaItem:
    title: str
    rationale: str
    priority: str = "medium"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_agent_session_runtime.AgentSessionContractTests.test_agent_session_trace_includes_agenda_and_runtime_metadata -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_session_runtime.py app/core/session.py
git commit -m "test: lock agent session contract"
```

### Task 2: Lock runtime agenda and degradation behavior with tests

**Files:**
- Modify: `tests/test_agent_session_runtime.py`
- Modify: `app/services/agent_runtime/runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_records_agenda_and_schema_errors_in_trace(self):
    from app.core.session import AgentSession
    from app.services.agent_runtime import AgentRuntime

    class AgendaLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, role, prompt, context):
            self.calls += 1
            if self.calls == 1:
                return LLMResult(content='{"agenda_add":[{"title":"Inspect ambiguity","rationale":"Need structure"}]}')
            return LLMResult(content="not json")

    session = AgentSession(task_id="task_1", step_id="machine_spec_compiler", agent_role="Compiler", goal="compile", max_iterations=2)
    result = AgentRuntime(llm=AgendaLLM()).run_json_session(
        session=session,
        prompt="Return JSON",
        required_keys=["primary_requirement"],
    )

    self.assertTrue(session.state.agenda_items)
    self.assertTrue(result.schema_errors)
    self.assertEqual(result.status.value, "blocked")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_agent_session_runtime.AgentRuntimeTests.test_runtime_records_agenda_and_schema_errors_in_trace -v`
Expected: FAIL because agenda operations and schema error summaries are not yet recorded.

- [ ] **Step 3: Write minimal implementation**

```python
if isinstance(structured.get("agenda_add"), list):
    for item in structured["agenda_add"]:
        session.add_agenda_item(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_agent_session_runtime.AgentRuntimeTests.test_runtime_records_agenda_and_schema_errors_in_trace -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_session_runtime.py app/services/agent_runtime/runtime.py
git commit -m "test: lock agent runtime agenda behavior"
```

### Task 3: Reconcile workflow compatibility and run regressions

**Files:**
- Modify: `app/workflows/spec_to_agent.py`
- Modify: `app/workflows/acceptance_review.py`
- Test: `tests/test_spec_to_agent.py`
- Test: `tests/test_acceptance_review.py`

- [ ] **Step 1: Write the failing regression expectation**

```python
self.assertIn("allowed_tools", result.outputs["agent_session_trace"])
self.assertIn("agenda_items", result.outputs["agent_session_trace"]["state"])
```

- [ ] **Step 2: Run regression tests to verify gaps**

Run: `python3 -m unittest tests.test_spec_to_agent tests.test_acceptance_review -v`
Expected: Either PASS with missing assertions removed or FAIL where trace shape assumptions need to be updated compatibly.

- [ ] **Step 3: Write minimal compatibility implementation**

```python
trace = run_result.session.to_trace()
outputs = {
    "agent_session_id": session.session_id,
    "agent_session_trace": trace,
}
```

- [ ] **Step 4: Run regressions to verify they pass**

Run: `python3 -m unittest tests.test_agent_session_runtime tests.test_spec_to_agent tests.test_acceptance_review tests.test_backend_phase1 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/workflows/spec_to_agent.py app/workflows/acceptance_review.py tests/test_spec_to_agent.py tests/test_acceptance_review.py tests/test_backend_phase1.py
git commit -m "feat: upgrade agent session runtime core"
```
