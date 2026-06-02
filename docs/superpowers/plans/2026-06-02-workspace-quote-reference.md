# Workspace Quote Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Codex-like quote references to Workspace so users can select text from the conversation area or editor, attach it as one aggregated quote pill above the composer, and send the message with source metadata.

**Architecture:** Keep the UI interaction in the Workspace frontend, but extract quote normalization and aggregation into a small pure helper module that can be tested with Node’s built-in test runner. Extend the decision request DTO so the frontend can submit structured quote metadata without changing existing plain-text behavior.

**Tech Stack:** React 19, Vite, Lucide, FastAPI, Pydantic/dataclasses, Node built-in test runner

---

### Task 1: Extract quote aggregation helpers

**Files:**
- Create: `frontend/src/pages/Workspace/quoteSelection.js`
- Test: `frontend/src/pages/Workspace/quoteSelection.test.js`

- [ ] **Step 1: Write the failing test**

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildQuoteDraft,
  summarizeQuoteDraft,
  appendQuoteDraft,
  clearQuoteDraft,
  buildDecisionPayload,
} from './quoteSelection.js';

test('appendQuoteDraft aggregates multiple selections into one draft', () => {
  const first = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'First line',
  });
  const second = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: 'Second line',
  });

  const combined = appendQuoteDraft(null, first);
  const updated = appendQuoteDraft(combined, second);

  assert.equal(updated.items.length, 2);
  assert.equal(summarizeQuoteDraft(updated), '2 个已选文本片段');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/src/pages/Workspace/quoteSelection.test.js`
Expected: FAIL with module not found or missing export

- [ ] **Step 3: Write minimal implementation**

Create a helper module exporting normalized quote builders, summary text generation, append/clear helpers, and a `buildDecisionPayload()` function that conditionally injects `quoted_selections`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/src/pages/Workspace/quoteSelection.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Workspace/quoteSelection.js frontend/src/pages/Workspace/quoteSelection.test.js
git commit -m "feat: add workspace quote selection helpers"
```

### Task 2: Extend decision payload contract

**Files:**
- Modify: `app/api/schemas.py`
- Modify: `app/core/context.py`
- Modify: `app/services/task_service.py`
- Modify: `app/api/server.py`
- Modify: `docs/refactor/api-contract.md`

- [ ] **Step 1: Write the failing test**

Add a backend unit test covering that a decision payload can include `quoted_selections` and is persisted in `TaskContext.user_decisions`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_backend_phase1 -v`
Expected: FAIL on missing `quoted_selections`

- [ ] **Step 3: Write minimal implementation**

Add an optional `quoted_selections` field to the request DTO and `UserDecision`, then thread it through `TaskService.apply_decision()` and the FastAPI route without changing current callers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_backend_phase1 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/schemas.py app/core/context.py app/services/task_service.py app/api/server.py docs/refactor/api-contract.md
git commit -m "feat: persist quoted selections in task decisions"
```

### Task 3: Integrate unified quote UI in Workspace

**Files:**
- Modify: `frontend/src/pages/Workspace/index.jsx`
- Modify: `frontend/src/pages/Workspace/workspace.css`
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Write the failing test**

Extend `frontend/src/pages/Workspace/quoteSelection.test.js` with payload-shaping and aggregation cases that match the UI behavior.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/src/pages/Workspace/quoteSelection.test.js`
Expected: FAIL on the new UI-oriented helper expectations

- [ ] **Step 3: Write minimal implementation**

Replace editor-only quote insertion with a shared selection capture flow, store one aggregated quote draft in Workspace state, render a Codex-like pill above the textarea, add remove/clear behavior, and submit `quoted_selections` with the decision API call.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test frontend/src/pages/Workspace/quoteSelection.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Workspace/index.jsx frontend/src/pages/Workspace/workspace.css frontend/src/api.js frontend/src/pages/Workspace/quoteSelection.test.js
git commit -m "feat: add workspace quote references"
```

### Task 4: Verify end-to-end buildability

**Files:**
- Verify only

- [ ] **Step 1: Run targeted backend validation**

Run: `python3 -m unittest tests.test_backend_phase1 -v`
Expected: PASS

- [ ] **Step 2: Run Python compile validation**

Run: `python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/services/*.py app/api/*.py`
Expected: no output

- [ ] **Step 3: Run frontend tests**

Run: `node --test frontend/src/pages/Workspace/quoteSelection.test.js`
Expected: PASS

- [ ] **Step 4: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: build succeeds

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-06-02-workspace-quote-reference.md
git commit -m "docs: add workspace quote reference plan"
```
