# 04 状态与上下文

## 1. 两类状态

Evoloop 2.0 需要区分任务持久化状态和 Agent 运行时共识。

| 状态 | 生命周期 | 负责人 | 用途 |
|---|---|---|---|
| TaskContext | 跨请求持久化 | TaskService | 任务元数据、输入、用户裁决、产物索引、历史事件引用 |
| BlackboardState | 单次 DAG 执行期，checkpoint 快照 | Main Orchestrator | 当前共识、草稿、风险、架构决策、规则快照 |

## 2. TaskContext

```text
TaskContext
  task_id
  workspace_id
  task_type
  title
  goal
  inputs
  source_materials[]
  artifact_refs[]
  user_decisions[]
  dag_runs[]
  evidence_refs[]
  rule_candidate_refs[]
```

TaskContext 不应该存放大量文档正文和原始材料；它只保存引用和安全摘要。

## 3. BlackboardState

```text
BlackboardState
  version
  global_objective
  normalized_requirements
  service_topology
  api_contracts
  working_drafts
  discovered_risks
  architecture_decisions
  acceptance_criteria
  active_rules
  knowledge_context
  agent_outputs
```

每个字段声明 `merge_policy`：

| Policy | 行为 |
|---|---|
| `IMMUTABLE` | 创建后不可被 Agent 修改。 |
| `LAST_WRITE_WINS` | 单 owner 字段可覆盖。 |
| `KEY_PARTITIONED` | Dict 按 Agent 或节点 key 分区写入。 |
| `APPEND_DEDUP` | 追加并去重。 |
| `CONFLICT_ESCALATE` | 冲突进入仲裁或 Takeover。 |

## 4. Context Slice

主控不能把完整 Blackboard 透传给每个 Agent。Context Slice 按 SlotContract 精确裁切：

```text
ContextSlice = pick(BlackboardState, SlotContract.required_context_keys + optional_context_keys)
             + task_objective
             + allowed_tool_summaries
             + knowledge citations
```

好处：

- 减少 token 和成本。
- 降低幻觉和跨领域污染。
- 让脏节点传播可计算。
- 避免向第三方 Agent 泄露无关材料。

## 5. Merge 流程

```text
Subagent returns payload based_on_version=N
  -> Orchestrator checks current blackboard.version
  -> SchemaValidator validates output
  -> MergeEngine applies field merge_policy
  -> OK: version += 1
  -> STALE: mark node stale / rerun
  -> CONFLICT: emit arbitration.requested or takeover.suggested
```

## 6. Checkpoint

Checkpoint 应至少保存：

```text
checkpoint.json
  task_id
  dag_run_id
  last_completed_node_ids[]
  pending_node_ids[]
  stale_node_ids[]
  blackboard_snapshot_ref
  context_version
  event_offset
  status
```

恢复时以 checkpoint 为准，不从日志文本推断状态。

## 7. 用户决策写入

用户裁决、接管和终稿编辑不能直接篡改 Agent 历史输出。它们应作为新的事实进入 TaskContext/Blackboard：

```text
UserDecision
  decision_id
  applies_to
  selected_option
  text
  quoted_selections[]
  affected_fields[]
  created_at
```

随后通过 DirtyPropagation 决定哪些下游节点需要重跑。
