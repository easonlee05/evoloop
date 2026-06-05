# 00 Evoloop 3.1 AgentSession 技术演进路线

> 状态：当前实施路线。
> 取代：`docs/evoloop-3.0/technical/01-engineering-evolution.md` 作为 agent 能力建设的最新工程基准。

## 1. 当前判断

当前实现主要是 Playbook-first workflow：

```text
WorkflowEngine
  -> StepExecutor
  -> LLM.invoke
  -> JSON parsing / fallback
  -> StepResult
```

这套结构的优点是稳定、可恢复、可审计；缺点是 `type="agent"` 的步骤还不是 Agent，只是函数式 Executor。

3.1 的技术目标是演进为：

```text
WorkflowEngine
  -> AgentStepExecutor
  -> AgentRuntime.run(AgentSession)
      -> LLM.invoke_with_tools
      -> ToolService.invoke
      -> schema validation
  -> StepResult
```

## 2. 主要变动层级

主要变动在 Service 层。

| 层级 | 变动大小 | 说明 |
|---|---:|---|
| Service | 大 | 新增 `app/services/agent_runtime/`，承载多轮推理、tool use、schema validation |
| Workflow | 中 | Executor 变薄，创建 AgentSession 并委托 AgentRuntime |
| Core | 小到中 | 新增 `AgentSession`、`AgentDefinition`、运行结果契约 |
| LLM Port | 小但关键 | 增加 `invoke_with_tools()`，支持 native tool use |
| Tool/Governance | 小 | 复用 ToolService，补 session 维度审计和策略判断 |
| API/SSE | 小 | trace 中展示 session、iteration、tool calls、degraded 状态 |
| Frontend | 小 | 只消费结构化 trace 字段，不改视觉样式 |

## 3. 文件责任规划

### 3.1 Core

```text
app/core/session.py
  AgentSession
  AgentMessage
  AgentSessionState
  AgentRunResult

app/core/agent.py
  AgentDefinition
  AgentRole
  AgentOutputSchema
  AgentDegradationPolicy
```

这些文件只定义契约，不调用 LLM、不访问文件、不执行工具。

### 3.2 Service

```text
app/services/agent_runtime/__init__.py
app/services/agent_runtime/runtime.py
  AgentRuntime

app/services/agent_runtime/context_builder.py
  SessionContextBuilder

app/services/agent_runtime/tool_bridge.py
  ToolBridge

app/services/agent_runtime/schema_validator.py
  SchemaValidator
```

`AgentRuntime` 是新增核心。

### 3.3 LLM Port

```text
app/core/ports.py
  LLMPort.invoke_with_tools(...)
  LLMToolCall
  LLMToolResultMessage

app/services/llm.py
  OpenAILLM.invoke_with_tools(...)
```

保留 `invoke()` 兼容现有 playbook，新增 `invoke_with_tools()` 给 AgentRuntime 使用。

### 3.4 Workflow

```text
app/workflows/executors.py
  AgentStepExecutor 接入 AgentRuntime

app/workflows/spec_to_agent.py
  OpenQuestionIdentifierExecutor 变薄
  MachineSpecCompilerExecutor 变薄
```

第一阶段只改两个 executor，避免一次性迁移所有 agent 步骤。

## 4. AgentRuntime 行为规范

### 4.1 输入

`AgentRuntime.run()` 接收：

```text
AgentSession
Task
WorkflowStep
TaskDefinition
TaskContext
```

### 4.2 循环

```text
for iteration in range(max_iterations):
  response = llm.invoke_with_tools(messages, tools)

  if response.tool_calls:
    for call in response.tool_calls:
      result = ToolService.invoke(...)
      append observation message
    continue

  validation = SchemaValidator.validate(response.final_output)
  if validation.ok:
    return succeeded

  if validation.recoverable:
    append validation feedback
    continue

  return failed_or_degraded
```

### 4.3 输出

`AgentRunResult` 必须包含：

```text
session_id
status: succeeded | failed | degraded
final_output
summary
iterations
used_tools[]
schema_errors[]
degradation_reason
```

`StepResult` 应引用 `agent_session_id`，并在 degraded 时显式暴露。

## 5. ToolPolicy 规则

3.1 不允许 AgentRuntime 直接执行工具。

所有工具必须通过：

```text
ToolBridge
  -> ToolService.invoke
  -> ToolPolicy check
  -> ToolResult
```

策略判断至少包含：

```text
task_type
step_id
agent_role
session_id
tool_name
operation_kind
```

第一阶段可先把 session 维度用于审计，不必一次性实现复杂策略矩阵。

## 6. 事件与可观测性

新增事件类型建议：

```text
agent.session.started
agent.session.iteration.started
agent.session.tool.requested
agent.session.tool.observed
agent.session.schema.validated
agent.session.degraded
agent.session.completed
agent.session.failed
```

事件 payload 原则：

- 可以展示工具名、状态、摘要、耗时。
- 不展示凭证。
- 不展示完整本地路径。
- 不展示未授权材料原文。
- 不要求展示完整 chain-of-thought。

## 7. 第一阶段迁移目标

第一阶段只迁移：

1. `open_question_identifier`
2. `machine_spec_compiler`

成功标准：

- 两个步骤都通过 AgentRuntime 执行。
- 每个步骤有独立 AgentSession ID。
- 失败不再静默 fallback 为假成功。
- schema validation 失败可观测。
- 现有 `WorkflowEngine` checkpoint/resume 不被破坏。
- `tests/test_spec_to_agent.py` 和 `tests/test_backend_phase1.py` 继续通过或按新契约更新。

## 8. 第二阶段迁移目标

第二阶段再迁移：

- `agent_package_generator`
- `acceptance_protocol_generator`
- `acceptance_review` 中的只读 reviewer agent
- 只读 `workspace.inspect` 工具
- peer result bundle intake

## 9. PeerAdapter 接入原则

不要在第一阶段接真实 AI 技术同事 handler。

PeerAdapter 的命名表示“同事协作适配器”，不表示 Codex、Claude Code、Cursor 或 Antigravity 是数字 PM 的下游。它只是把规格、任务包、验收协议和结果包转换成各协作工具能理解的接口。

原因：

- 当前 agent package 质量仍依赖一次性 prompt 和 fallback。
- 过早自动执行会放大低质量 package 的风险。
- 应先让 spec 编译与 package 生成可信，再接 Codex / Claude Code / Cursor。

PeerAdapter 协作接入顺序：

```text
agent package schema stable
  -> peer target selection stable
  -> result bundle schema stable
  -> local dry-run handler
  -> real Codex/Claude/Cursor/Antigravity handler
  -> acceptance review loop
```

## 10. 验证命令

文档改动后至少运行：

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```

涉及前端 API trace 字段时再运行：

```bash
npm --prefix frontend run build
```

## 11. 实施基准

后续 AI 技术同事读项目时，必须把以下文件作为最新实施基准：

1. `AGENTS.md`
2. `AGENT_MAP.md`
3. `docs/evoloop-3.1/README.md`
4. `docs/evoloop-3.1/architecture/00-global-architecture.md`
5. `docs/evoloop-3.1/technical/00-agent-session-evolution.md`

若旧文档与这些文件冲突，以 3.1 文件为准。
