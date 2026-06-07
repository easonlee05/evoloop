# AgentSession Core Design

## Goal

Upgrade Evoloop 3.1 `AgentSession` from a thin bounded-JSON wrapper into a real single-step runtime contract with auditable state, agenda tracking, runtime metadata, and explicit degraded/blocked outcomes.

## Scope

This design covers:

- `app/core/session.py`
- `app/services/agent_runtime/runtime.py`
- Existing workflow step integrations that already consume `agent_session_id` and `agent_session_trace`
- Backend tests that define the `AgentSession` contract

This design does not cover:

- Peer/subagent dispatch
- Cross-step or cross-task agent memory
- Product memory / GBrain integration
- Workflow topology changes

## Architecture

Evoloop 3.1 keeps the outer control plane deterministic:

- Playbook controls workflow topology
- `AgentSession` controls bounded reasoning inside one step
- `ToolPolicy` continues to gate external capabilities
- Workflow executors continue to consume structured `AgentRunResult`

The implementation will preserve the current `run_json_session()` entrypoint, but the internals will be upgraded into a true runtime loop that owns session state transitions, agenda recording, tool execution metadata, schema recovery, and final result summarization.

## Core Model Changes

### AgentSession

`AgentSession` will continue to represent one workflow step execution, but it will now also carry:

- `allowed_tools`
- `output_schema_keys`
- `context_budget`
- `final_output`
- `updated_at`

This lets the session itself express what it is allowed to do and what it ultimately produced, instead of scattering that information across runtime locals.

### AgentSessionState

`AgentSessionState` will be expanded with:

- `agenda_items`
- `tool_call_count`
- `final_output_summary`
- `degradation_reason`
- `updated_at`

These fields make the trace explainable without exposing private chain-of-thought.

### AgendaItem

A new `AgendaItem` value object will exist only inside the current session and will support:

- `item_id`
- `title`
- `rationale`
- `status`
- `priority`
- `note`
- `created_at`
- `updated_at`

Agenda is only an internal analysis helper. It never changes workflow steps, never creates checkpoints, and never crosses a decision gate.

### AgentRunResult

`AgentRunResult` will be expanded with:

- `summary`
- `used_tools`
- `schema_errors`
- `iterations`

This lets workflow executors and APIs consume a richer runtime outcome without reconstructing it from raw trace data.

## Runtime Behavior

`AgentRuntime.run_json_session()` will remain the integration entrypoint, but it will evolve into a proper session controller:

1. Initialize session state and derived permissions
2. Run bounded model turns
3. Record turn-level metadata and observations
4. Apply agenda operations if present
5. Execute allowed tool calls only through `ToolService`
6. Recover from schema failures within bounded retries
7. Return either schema-valid output or an explicit blocked/degraded result

## Agenda Protocol

The first implementation will keep agenda as a runtime-controlled protocol instead of first-class public tools.

The model may emit lightweight agenda operations such as:

- `agenda_add`
- `agenda_update`

The runtime will validate these operations, enforce a small item limit, and store them on the session state. Agenda operations do not directly trigger external tools.

## No Fake Success Rules

This design preserves the 3.1 rule that the runtime may degrade, but may not fabricate success:

- schema exhaustion returns `blocked`
- denied tool use returns `blocked`
- failed tool use returns `blocked`
- degraded state must surface `degradation_reason`
- final traces must show what failed and why

## Trace Shape

`AgentSession.to_trace()` should expose:

- session identity and scope
- allowed tools and output schema keys
- state summary
- agenda items
- turns
- observations
- final output summary
- degradation/error metadata

The trace remains audit-oriented and does not expose private reasoning.

## Testing Strategy

The implementation will follow TDD in three stages:

1. Contract tests for the upgraded `AgentSession`, `AgendaItem`, and `AgentRunResult`
2. Runtime tests for agenda recording, schema recovery metadata, tool accounting, and degradation summaries
3. Regression tests for existing `spec_to_agent` and `acceptance_review` integrations

## Compatibility

- Keep `run_json_session()` as the runtime entrypoint for existing workflows
- Preserve current `agent_session_trace` consumers
- Add fields compatibly instead of reshaping existing keys destructively
