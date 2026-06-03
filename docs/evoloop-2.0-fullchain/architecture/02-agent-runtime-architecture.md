# 02 Agent Runtime 架构

## 1. 运行时定位

Agent Runtime 是 Evoloop 2.0 的执行内核。它负责把一个任务计划转换为结构化的多 Agent 协作过程，并在用户可见、可控、可恢复的前提下完成交付。

它必须同时满足：

- 动态装载不同 Agent 组合。
- 严格限制 Agent 权限。
- 保证状态可合并、可回放、可恢复。
- 兼容用户裁决、Takeover 和终稿学习闭环。

## 2. 运行时核心组件

| 组件 | 职责 |
|---|---|
| Main Orchestrator | 规划 DAG、调度节点、收集结果、触发仲裁、推进任务。 |
| Agent Registry | 加载 Slot、Agent 实现、Contract、扩展包覆盖关系。 |
| Event Bus | 派发消息、维护 hop/llm 预算、桥接 SSE。 |
| Context Slicer | 为节点构造最小上下文。 |
| Merge Engine | 将 Subagent 输出合并回 Blackboard。 |
| Tool Service | 受控执行材料、知识、产物、Diff 等能力。 |
| Schema Validator | 校验节点输出和信封内容。 |

## 3. 运行时对象

```text
AgentSlot
  slot_name
  contract_version
  implementation
  action_type: CORE | OVERRIDE | APPEND

SlotContract
  slot_name
  version
  required_context_keys[]
  optional_context_keys[]
  output_schema
  merge_targets[]

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
```

## 4. Main Orchestrator 职责分解

Main Orchestrator 只做控制面，不做专业内容生成。它负责：

1. 读取 RuntimeProfile。
2. 选择或生成 TaskDAG。
3. 调用 Context Slicer 构造每个节点输入。
4. 通过 Event Bus 派发节点消息。
5. 校验节点输出 schema。
6. 调用 Merge Engine 合并结果。
7. 处理失败、重试、仲裁、暂停与恢复。
8. 在合适节点触发 Artifact 写入、Evidence 冻结和后置 DAG。

它不应该：

- 直接读写文件。
- 直接调用 GBrain HTTP/MCP。
- 直接拼接最终用户文档正文。
- 绕过 ToolService 操作外部系统。

## 5. Agent Registry

### 5.1 装载内容

Registry 需要同时装载：

- Core Pack 基础 Slot。
- Domain Pack 的覆盖和新增。
- Expansion Pack 的覆盖和新增。
- SlotContract 元数据。
- output schema registry。

### 5.2 校验内容

Registry 校验至少包括：

- 重复 Slot 定义是否合法。
- Override 是否兼容现有 contract。
- 所有 output schema 是否存在。
- Agent manifest 是否声明允许的工具。
- 是否存在未满足的依赖 Slot。

### 5.3 产出

Registry 产出的是一个可执行的 `ActiveRegistrySnapshot`：

```text
ActiveRegistrySnapshot
  active_slots{}
  contracts{}
  output_schemas{}
  pack_lineage[]
```

Task 运行期间以 snapshot 为准，避免中途加载变更导致行为漂移。

## 6. Message Envelope 与 Session Budget

### 6.1 为什么需要信封协议

Agent 间不能直接传自然语言，因为这会导致：

- 上下文范围失控。
- 消息不可验证。
- 预算不可追踪。
- 前端无法结构化展示。

因此所有 Agent 通信都必须通过 `MessageEnvelope`。

### 6.2 Session Budget

Event Bus 为每个子任务会话维护预算：

```text
SessionBudget
  session_id
  max_hops
  max_llm_calls
  max_tokens
  max_tool_calls
  current_hops
  current_llm_calls
  current_tokens
```

预算由总线维护，不暴露给 Agent，以防止 Agent 伪造或重置预算。

## 7. Subagent 执行契约

Subagent 只应感知：

- 目标节点的 `task_objective`
- 最小 `context_slice`
- 允许调用的 Tool 名称
- 预期输出 schema

Subagent 返回结构化结果：

```json
{
  "status": "succeeded",
  "slot": "Biz_Analyst",
  "based_on_blackboard_version": 4,
  "payload": {
    "architecture_decisions": [
      "首期使用异步风控校验加事后对账"
    ],
    "review_notes": [
      "需要把退款链路纳入异常处理"
    ]
  },
  "tool_calls": []
}
```

## 8. Tool 调用边界

Subagent 的一切外部能力都来自 Tool Service：

- `material.read`
- `material.parse`
- `artifact.read`
- `artifact.write`
- `knowledge.query`
- `knowledge.search`
- `knowledge.find_contradictions`
- `diff.extract_rules`

Agent 不允许：

- 任意 shell
- 任意网络
- 任意路径读写
- 直接写 GBrain

## 9. 输出校验与重试

### 9.1 校验链

```text
Subagent returns payload
  -> envelope schema validation
  -> output schema validation
  -> merge target validation
  -> budget accounting
  -> merge or reject
```

### 9.2 重试策略

- 结构不合法：自动重试，最多 2 次。
- Tool denied：不重试，直接失败或 blocked。
- 预算超限：不重试，进入 blocked / takeover。
- 基于旧版本状态：标记 stale，必要时重跑。

## 10. 并行执行模型

Evoloop 2.0 允许多个节点并行，但并行不等于共享写入：

- 每个节点读取自己的 blackboard snapshot。
- 返回时声明 `based_on_blackboard_version`。
- Merge Engine 串行写入。
- 如写入字段冲突，交给 merge policy 或用户仲裁处理。

这能避免“两个 Agent 同时写全局结论”导致的非确定性。

## 11. 与平台层的关系

Agent Runtime 是平台内核，但它不是平台本身：

- Workspace 选择哪些 Agent 可用。
- API 决定何时创建任务、保存终稿、发起审核。
- GBrain 提供长期知识。
- RuleService 治理候选法则。

Runtime 的职责始终局限于“把当前这个任务执行完，并把结果结构化交给别的层”。
