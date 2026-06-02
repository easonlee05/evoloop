# 工作流与 Tool 架构

当前 EvoLoop 的任务执行内核由 `WorkflowEngine` 和 `ToolService` 组成：前者负责解释任务步骤，后者负责提供受控能力并输出审计事件。

## 任务定义

每个任务类型都由一个 `TaskDefinition` 描述，关键字段包括：

- `type`
- `display_name`
- `input_schema`
- `workflow`
- `tool_policy`
- `round_policy`
- `gate_policy`
- `output_spec`

当前注册表位于 `app/workflows/definitions.py`，只注册两类任务：`manual` 和 `prd`。

## WorkflowStep 类型

当前引擎支持以下步骤类型：

| 类型 | 当前用途 |
|---|---|
| `context` | 构建上下文、解析材料、检索知识 |
| `agent` | 调用 PM / Tech / QA / Reviewer / Writer |
| `gate` | 根据当前历史结果做门禁判断 |
| `arbitration` | 生成裁决包并暂停任务 |
| `artifact` | 写入文档产物 |
| `diff` | 规则提炼占位步骤 |
| `checkpoint` | 保存 checkpoint |

## 当前执行机制

```text
TaskService.run_task
  -> WorkflowEngine.run
  -> 依次读取 WorkflowSpec.steps
  -> 同 parallel_group 的步骤并行执行
  -> 每个成功步骤写入 step_outputs 和 checkpoint
  -> 需要裁决时切换 waiting_for_user
  -> artifact 步骤统一写入文档
```

### 并行组

当多个步骤有相同 `parallel_group` 时，引擎会并发执行。当前主要用于：

- `prd` 里的 `Tech` / `QA` 并行评审
- `manual` 里的 `Tech` / `QA` 并行校验

### checkpoint

成功步骤完成后，引擎会保存：

- `last_completed_step_id`
- `next_step_id`
- `status`

任务恢复时，如果存在 checkpoint，就从 `next_step_id` 继续执行。

## Agent 步骤

Agent 步骤的当前行为：

- 从 `TaskContext` 组装 `llm_context`
- 调用 `invoke_stream` 流式获取输出
- 逐块写入 `agent.message.chunk` 事件
- 完成后写入 `agent.message.completed`
- 把内容记录到 `round_history`

Writer 步骤还有一个当前可见的兜底逻辑：

- 如果模型输出满足结构要求，直接拿模型内容作为文档
- 如果模型输出太短或结构不足，回退到 `_render_prd()` 或 `_render_manual()` 生成稳定 Markdown

## Gate 与仲裁

当前 `gate` 主要负责两类判断：

- 普通门禁：记录 `pass` 结果和检查项
- `convergence_gate`：判断 `prd` 是否收敛

当 `convergence_gate` 判定需要用户参与时：

- 返回 `StepStatus.NEEDS_ARBITRATION`
- 生成 `dispute_package`
- 任务状态变为 `waiting_for_user`
- 前端提交决策后从 `resume_step_id` 继续执行

## ToolService

`ToolService` 维护三部分内容：

- `ToolSpec`
- handler
- `ToolPolicy`

当前默认工具清单：

| Tool | 作用 |
|---|---|
| `material.read` | 读取材料摘要 |
| `material.parse` | 解析上传材料 |
| `knowledge.retrieve` | 检索知识摘要 |
| `artifact.write` | 写入 Markdown artifact |
| `artifact.read` | 读取 artifact |
| `artifact.backup` | 备份 artifact |
| `format.validate` | 校验格式 |
| `diff.extract_rules` | 规则提炼占位 |
| `event.emit` | 统一输出事件 |

## 权限与审计

Tool 调用遵循以下规则：

- 只有 `TaskDefinition.tool_policy` 允许的工具才能执行
- 不允许时返回 `ToolResult.status = denied`
- 所有调用都会输出 `tool.call.started`
- 成功时输出 `tool.call.completed`
- 失败时输出 `tool.call.failed`
- 被拒绝时输出 `tool.call.denied`

## 事件流

当前前端重点消费这些事件：

- `workflow.step.started`
- `agent.message.chunk`
- `agent.message.completed`
- `arbitration.requested`
- `arbitration.applied`
- `artifact.created`
- `task.completed`
- `task.cancelled`
- `task.failed`
- `tool.call.denied`

事件内容只传结构化摘要，不传凭证、完整本地路径或未授权材料原文。
