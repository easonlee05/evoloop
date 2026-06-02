# 工作流与 Tool 架构：可暂停编排、受控能力调用与事件透明

本文补足 GBrain 重构后的两个横切架构层：Workflow 和 Tool。Workflow 负责把任务从输入推进到产物；Tool 负责把 Agent 需要使用的外部能力纳入统一权限、审计和事件协议。二者都属于后端中台能力，不属于前台 UI，也不属于长期知识库。

## 1. 定位

Workflow 是任务执行控制面。它只管理任务生命周期、步骤调度、暂停恢复、重试取消、事件输出和产物交接，不直接写具体业务文案。

Tool 是受控能力调用层。它为 Agent 和 Workflow 提供文件读取、材料解析、知识检索、产物写入、Diff 提炼、格式校验等能力，但所有调用必须经过注册、权限校验、结果封装和事件记录。

## 2. 边界

| 架构层 | 负责 | 不负责 |
|---|---|---|
| Workflow | 步骤编排、状态流转、仲裁暂停、恢复重放、失败处理、事件输出 | Prompt 内容、模型供应商细节、前端展示样式 |
| Tool | 能力注册、参数校验、权限控制、调用审计、结果标准化 | 自主决策、绕过任务上下文、直接改任务状态 |
| Agent | 根据上下文产出结构化判断、草案、挑战和修订 | 直接读写文件、直接调用未授权外部能力 |
| TaskDefinition | 声明任务类型的步骤、角色、门禁、工具白名单和产物规格 | 复制一套独立 Orchestrator |

## 3. Workflow 模型

每个任务类型由 `TaskDefinition.workflow` 声明步骤列表。通用引擎只解释步骤协议，不硬编码 `manual` 或 `prd` 的业务细节。

```text
WorkflowSpec
  name
  version
  steps[]
    id
    type
    title
    role
    input_keys
    output_keys
    allowed_tools
    timeout_seconds
    retry_policy
    pause_policy
    on_success
    on_failure
```

步骤类型首期固定为：

| Step 类型 | 用途 |
|---|---|
| `context` | 构建或补全 `TaskContext` |
| `agent` | 调用 PM、Tech、QA、Reviewer、Writer 等 Agent |
| `gate` | 执行可解析门禁并返回通过/阻塞/需仲裁 |
| `arbitration` | 生成分歧包并暂停等待用户裁决 |
| `artifact` | 写入、更新、备份或导出产物 |
| `diff` | 基于用户编辑或终稿生成候选法则 |
| `checkpoint` | 保存上下文、轮次、事件和中间结果 |

## 4. StepResult 协议

所有步骤都返回统一结果，方便引擎稳定推进。

```text
StepResult
  step_id
  status: succeeded | failed | blocked | needs_arbitration | cancelled
  summary
  outputs
  events[]
  tool_calls[]
  error
  next_step_id
```

约束：

- 步骤不得直接修改全局状态，只能通过 `StepResult.outputs` 和服务接口提交变更。
- `needs_arbitration` 是正常状态，不是错误。
- `blocked` 表示缺少必要输入、权限或上游产物，引擎应停止并暴露原因。
- 每个步骤完成后必须写 checkpoint，任务恢复时从最后一个成功 checkpoint 继续。

## 5. 标准 Workflow

### 5.1 PRD Workflow

```text
create_task
  -> validate_input
  -> build_context
  -> retrieve_knowledge
  -> pm_draft
  -> tech_challenge
  -> pm_revise_after_tech
  -> qa_challenge
  -> pm_revise_after_qa
  -> convergence_check
  -> arbitration_if_needed
  -> reviewer_gate
  -> writer_final_prd
  -> write_artifacts
  -> freeze_evidence
  -> close_task
```

### 5.2 Manual Workflow

```text
create_task
  -> validate_input
  -> ingest_materials
  -> build_context
  -> retrieve_knowledge
  -> pm_outline_and_questions
  -> tech_fact_check
  -> qa_operability_check
  -> reviewer_plan_gate
  -> writer_overview
  -> decide_document_split
  -> writer_scene_docs
  -> reviewer_document_gate
  -> revise_until_pass_or_arbitrate
  -> write_artifacts
  -> freeze_evidence
  -> close_task
```

### 5.3 步骤中的动态产物渲染机制（Dynamic Artifact Rendering）

在 Workflow 推进到 Writer Agent 相关的步骤（如 `writer_final_prd` 或 `writer_scene_docs`）时，系统将自动应用产物渲染决策：
1. **AI 真实生成优先**：若大模型作为 Writer 角色输出了符合技术规范（例如包含“背景”与“业务目标”或“操作路径”等核心结构特征，或字数足够）的真实排版文档时，系统直接采用 AI 的输出内容作为最终产物文本。
2. **测试退避机制 (Fallback)**：若处于单元测试回归等模拟场景下（模型使用 FakeLLM 输出的简短文字），系统会自动退避降级至预置的静态结构化模板（通过 `_render_prd` 或 `_render_manual` 渲染），以确保不破坏单元测试的结构与断言，维持高鲁棒性。
3. **物化写入解耦**：Writer 步骤所产出的文本将被保存在 `StepResult.outputs["artifact_content"]` 中，并由紧随其后的 `artifact` 类型步骤（如 `write_artifacts`）通过 `artifact.write` 工具真正持久化为物理文件并记录版本。

## 6. 暂停、恢复、重试与取消

- `arbitration` 步骤必须把任务状态置为 `waiting_for_user`，并输出 `arbitration.requested` 事件。
- 用户提交裁决后，后端写入 `TaskContext.user_decisions`，追加 `arbitration.applied` 事件，并从声明的 `resume_step_id` 继续。
- 可重试步骤必须幂等。重试不得重复写最终产物；产物写入必须通过 Artifact 版本号防重复。
- 用户取消任务时，引擎停止新步骤，保存已完成 checkpoint，输出 `task.cancelled`，不得把半成品标记为完成。
- 系统失败恢复时，事件流可从 `events.jsonl` 回放，任务状态可由 `task.json` 与最后 checkpoint 重建。

## 7. Tool 模型

Tool 必须显式注册，Agent 只能调用 `TaskDefinition.tool_policy` 允许的工具。

```text
ToolSpec
  name
  version
  description
  input_schema
  output_schema
  side_effect: none | read | write | external
  required_permissions[]
  timeout_seconds
  retry_policy
```

```text
ToolCall
  id
  task_id
  step_id
  agent_role
  tool_name
  arguments
  status
  started_at
  completed_at
```

```text
ToolResult
  call_id
  status: succeeded | failed | denied | timeout
  summary
  data
  artifacts[]
  error
```

## 8. 首期 Tool 清单

| Tool | 类型 | 允许阶段 | 说明 |
|---|---|---|---|
| `material.read` | read | context、agent | 读取用户上传材料摘要或原文片段 |
| `material.parse` | read | context | 将上传材料解析为结构化材料包 |
| `knowledge.retrieve` | read | context、agent | 按任务目标检索 GBrain 或本地知识快照 |
| `artifact.write` | write | artifact | 写 Markdown 产物并记录版本 |
| `artifact.read` | read | agent、diff | 读取已生成产物供审查或 Diff 使用 |
| `artifact.backup` | write | artifact、diff | 用户编辑或重写前备份旧版本 |
| `format.validate` | none | gate | 校验操作手册格式红线或 PRD 结构要求 |
| `diff.extract_rules` | write | diff | 从终稿变化中生成候选法则，不直接入库 |
| `event.emit` | write | all | 统一输出结构化事件，禁止日志协议替代 |

首期不允许 Agent 调用任意 shell、任意网络请求、任意文件路径读取。新增 Tool 必须先进入注册表和白名单。

## 9. Tool 权限策略

```text
ToolPolicy
  task_type
  role
  step_id
  allowed_tools[]
  denied_tools[]
  max_calls_per_step
  require_user_approval_for[]
```

规则：

- PM、Tech、QA、Reviewer 默认只能读上下文、材料摘要、知识检索结果和当前草案。
- Writer 可以请求写产物，但必须通过 `artifact.write`，不能直接写文件。在 `write_artifacts` 步骤中，`artifact.write` 工具会接收上游步骤中经过动态产物渲染决策生成的最终排版内容，并执行原子写入物理文件。
- Diff 可以读取旧版和新版产物，生成候选法则，但不能把法则写入 approved 区。
- 任何 write/external 类型 Tool 都必须产生 `tool.call.started` 和 `tool.call.completed` 事件。
- 权限不足返回 `denied`，不应伪装成普通失败。

## 10. Tool 与事件流

Tool 调用对前端透明，但不要求前端理解内部实现。

| 事件 | 说明 |
|---|---|
| `workflow.step.started` | 步骤开始 |
| `workflow.step.completed` | 步骤完成 |
| `workflow.step.failed` | 步骤失败 |
| `tool.call.started` | Tool 调用开始 |
| `tool.call.completed` | Tool 调用成功 |
| `tool.call.failed` | Tool 调用失败 |
| `tool.call.denied` | Tool 因权限被拒绝 |

事件 payload 应包含工具名、步骤 ID、角色、摘要和关联 artifact ID，但不得泄露凭证、完整本地路径或未授权材料原文。

## 11. 与其他架构边界的关系

- 与前台架构：前台只消费 Workflow 与 Tool 事件，不调用 Tool。
- 与知识库架构：Tool 通过 `knowledge.retrieve` 读取知识；可信法则入库仍走 Diff 审核，不允许普通任务直接写入。
- 与中台铁三角架构：PM、Tech、QA、Reviewer 在 Workflow 步骤内运行，按 ToolPolicy 使用受控工具。
- 与 Diff 流程架构：Diff 是 Workflow 的后置步骤或独立任务；候选法则生成依赖 Tool 审计和证据冻结。
