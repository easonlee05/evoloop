# 04 状态与上下文架构

## 1. 设计原则

Evoloop 2.0 的状态设计必须解决两个问题：

1. Agent 需要共享任务共识，但不能互相污染。
2. 用户可以中途接管、修改事实、重跑局部节点，状态仍然要可解释。

因此系统必须区分“任务持久化状态”和“运行时共识状态”。

## 2. TaskContext 与 Blackboard 的职责分离

| 对象 | 生命周期 | 用途 |
|---|---|---|
| `TaskContext` | 跨请求、跨页面刷新 | 任务元信息、用户输入、裁决记录、artifact/evidence/rule refs |
| `BlackboardState` | 单个 DAG run 期间 | 当前执行共识、草稿、风险、架构决策、活跃规则 |

### 2.1 TaskContext

```text
TaskContext
  task_id
  workspace_id
  task_type
  title
  goal
  inputs
  source_material_refs[]
  user_decisions[]
  artifact_refs[]
  evidence_refs[]
  candidate_rule_refs[]
  degradation_state
```

### 2.2 BlackboardState

```text
BlackboardState
  version
  global_objective
  normalized_requirements
  knowledge_context
  active_rules
  working_drafts
  discovered_risks
  architecture_decisions
  acceptance_criteria
  reviewer_findings
  agent_outputs
```

## 3. 为什么不能只有一个 Context

如果把所有状态塞进单一对象，会出现：

- 持久化任务信息和临时 Agent 草稿耦合。
- 用户刷新页面后难以判断什么是当前真相。
- Diff 学习时无法清晰提取证据边界。
- Takeover 后很难识别哪些节点失效。

因此 Blackboard 必须成为独立的运行时状态对象。

## 4. 上下文裁切

Subagent 不应看到整个 Blackboard，而只看到与自己职责相关的切片。

```text
ContextSlice
  based_on_blackboard_version
  required fields from Blackboard
  selected knowledge snippets
  selected rule summaries
  node-specific task objective
```

这让系统具备：

- 最小权限原则。
- 更低 token 成本。
- 更清晰的脏节点传播。

## 5. Merge Policy

Blackboard 的字段必须显式声明合并策略。

| 策略 | 说明 |
|---|---|
| `IMMUTABLE` | 一经确定不可被节点覆盖，如 `global_objective`。 |
| `LAST_WRITE_WINS` | 适用于单 owner 状态。 |
| `KEY_PARTITIONED` | 不同 Agent 写不同 key。 |
| `APPEND_DEDUP` | 适用于风险列表、审查意见。 |
| `CONFLICT_ESCALATE` | 若两个节点写入冲突值，进入仲裁。 |

### 5.1 典型字段与策略

| 字段 | 策略 |
|---|---|
| `global_objective` | `IMMUTABLE` |
| `working_drafts` | `KEY_PARTITIONED` |
| `discovered_risks` | `APPEND_DEDUP` |
| `service_topology` | `CONFLICT_ESCALATE` |
| `reviewer_findings` | `APPEND_DEDUP` |

## 6. 版本控制

每次 Blackboard merge 成功后版本号加一。Subagent 返回时必须附带 `based_on_blackboard_version`。

```text
if result.based_on_blackboard_version < blackboard.version:
    result is stale
```

这样系统能知道：

- 某个节点结果是否基于过时事实。
- 是否需要重跑。
- 是否可以局部保留旧节点结果。

## 7. Checkpoint 体系

Checkpoint 是运行恢复的真相源，不应从日志“推断”。

```text
Checkpoint
  checkpoint_id
  task_id
  dag_run_id
  blackboard_snapshot_ref
  completed_node_ids[]
  running_node_ids[]
  stale_node_ids[]
  pending_node_ids[]
  waiting_reason
  last_event_offset
  created_at
```

恢复时流程：

```text
load checkpoint
  -> load blackboard snapshot
  -> replay event tail if needed
  -> reconstruct DAG node states
  -> resume from waiting/pending nodes
```

## 8. 用户裁决与 Takeover 进入状态层的方式

用户输入不是“覆盖历史”，而是新增事实。

### 8.1 Arbitration

```text
UserDecision
  decision_id
  applies_to_step_or_node
  selected_option
  text
  quoted_selections[]
  affected_fields[]
```

### 8.2 Takeover

Takeover 不应只记一段对话文本，而应写成结构化注入：

```text
TakeoverRecord
  takeover_id
  target_node_id
  modified_fields[]
  injected_facts{}
  created_by
  created_at
```

## 9. Dirty Propagation

当用户注入新事实后，需要找到哪些节点结果失效。

```text
for each completed node:
  if node.context_dependencies intersects modified_fields:
    mark node stale
    mark downstream nodes stale recursively
```

这样系统不必整图重跑，而能做局部修复。

## 10. 与终稿学习的关系

Artifact、UserDecision、ReviewerFinding、Blackboard 中的最终约束，都会成为 FrozenEvidence 的输入来源。

因此状态层必须保证：

- 用户编辑版本可追踪。
- 裁决记录可引用。
- Reviewer 驳回原因结构化保存。
- Blackboard 中真正达成共识的字段可被抽取。

否则 Diff 学习阶段拿不到可靠证据。
