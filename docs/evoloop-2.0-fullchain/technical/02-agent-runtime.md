# 02 核心 Agent 运行逻辑

本目录定义 Evoloop 2.0 最核心的 Agent Runtime。它是 PM-Agent 内核，但必须服从 Evoloop 平台的 Workspace、Tool、GBrain、Artifact 和审计边界。

## 1. 运行时组件

| 组件 | 职责 | 不负责 |
|---|---|---|
| Main Orchestrator | 生成/执行 DAG、裁切上下文、调度 Agent、合并结果、触发仲裁 | 直接读写文件、直接写 GBrain |
| Agent Registry | 加载 Slot、Agent 实现、SlotContract、扩展包覆盖关系 | 执行业务推理 |
| Subagent | 在限定 context_slice 内完成专业判断或生成结构化输出 | 修改全局状态、越权调用 Tool |
| Event Bus | 投递 MessageEnvelope、维护 SessionBudget、发布 SSE 事件 | 保存业务状态 |
| Tool Service | 执行受控能力、权限校验、审计 ToolCall | 自主决策 |
| Blackboard | 保存当前任务最高共识和中间结果 | 长期知识存储 |

## 2. Agent 生命周期

```text
Registry.load(domain_pack)
  -> Registry.validate(SlotContract)
  -> Orchestrator.plan(task)
  -> DAGValidator.validate(dag)
  -> Orchestrator.prepare_context_slice(node)
  -> EventBus.deliver(MessageEnvelope)
  -> Subagent.execute(envelope)
  -> Subagent.call_tool(...) if allowed
  -> Subagent returns structured payload
  -> Orchestrator.validate_output(schema)
  -> MergeEngine.merge(blackboard)
  -> EventBus emits node completed / conflict / failed
```

## 3. SlotContract

SlotContract 是 Agent 插槽的硬接口。任何 Agent 实现都必须声明自己实现了哪个 Slot 和哪个版本。

```text
SlotContract
  slot_name
  version
  required_context_keys[]
  optional_context_keys[]
  output_schema
  allowed_intents[]
  merge_targets[]
```

约束：

- Override Agent 不能偷偷增加 required context；需要新增输入就升级 contract version。
- DAG 节点引用的 Slot 必须存在于 active registry。
- Context Slice 必须满足 SlotContract 的 required keys。
- 输出必须通过 output_schema 校验后才能进入 Blackboard。

## 4. MessageEnvelope

所有 Agent 间通信都经过信封协议，不允许自然语言消息在系统内裸奔。

```text
MessageEnvelope
  msg_id
  parent_msg_id
  session_id
  sender_id
  recipient_id
  intent
  context_slice
  task_objective
  expected_output_format
  based_on_blackboard_version
  priority
  created_at
```

Event Bus 负责维护 `hop_count` 和 `SessionBudget`，Agent 不可篡改预算。

## 5. Subagent 执行规则

Subagent 输入只包含：

- 自己的 `context_slice`。
- 当前节点的 `task_objective`。
- SlotContract 允许的知识摘要或引用。
- ToolPolicy 允许的 Tool 名单。

Subagent 输出必须是结构化 payload，不允许直接提交全局状态修改：

```json
{
  "slot": "Reliability_Guard",
  "status": "succeeded",
  "payload": {
    "discovered_risks": [],
    "architecture_decisions": [],
    "review_notes": []
  },
  "tool_calls": []
}
```

## 6. ToolPolicy

Agent 不能直接读文件、写文件、访问网络或写 GBrain。所有能力走 Tool Service。

```text
ToolPolicy
  workspace_id
  task_type
  slot_name / role
  node_id
  allowed_tools[]
  denied_tools[]
  max_calls_per_node
  require_user_approval_for[]
```

典型权限：

| Agent | 允许 | 禁止 |
|---|---|---|
| Biz_Analyst | `knowledge.query`, `artifact.read` | `artifact.write`, `knowledge.put_page` |
| Reliability_Guard | `knowledge.search`, `material.read` | `artifact.write` |
| Copywriter/Writer | `artifact.read`, `artifact.write` | `knowledge.put_page` |
| Diff_Extractor | `knowledge.search`, `knowledge.find_contradictions` | `artifact.write`, `knowledge.put_page` |
| RuleService | `knowledge.find_contradictions`, `knowledge.put_page` | 直接绕过审核写入 |

## 7. 错误与熔断

- **SchemaInvalid**：Subagent 输出不符合 schema，主控最多重试 2 次。
- **ToolDenied**：权限不足，返回 denied，不伪装成 failed。
- **BudgetExhausted**：SessionBudget 超限，节点进入 blocked 或需要用户接管。
- **MergeConflict**：Blackboard 字段冲突，触发仲裁或 Takeover。
- **StaleResult**：Subagent 基于旧 Blackboard version 输出，需要重跑或丢弃。

## 8. 与现有 Phase 1 的关系

当前 `WorkflowEngine + TaskDefinition` 是 Phase 1 固定流水线。Evoloop 2.0 中它应逐步演进为：

```text
TaskDefinition.workflow.steps
  -> task_templates/*.yaml
  -> TaskDAG
  -> DAGNode(agent_slot, context_keys, output_schema)
```

在迁移期可以保留 `TaskService` 和现有 API，但内部执行应逐步接入 Registry、DAG、Blackboard 和 Event Bus。
