# 03 DAG 编排

## 1. 为什么需要 DAG

Evoloop 1.x 的固定流水线适合 `PM -> Tech -> QA -> Writer` 这类简单流程，但无法覆盖 2.0 的动态领域包、并行专家、用户接管和后置学习。2.0 以 DAG 表达执行计划。

## 2. DAG 来源

| 来源 | 说明 | 是否需要用户确认 |
|---|---|---|
| Template DAG | 开发者维护的确定性模板 | 可配置 auto_approve |
| LLM-filled DAG | 模板结构固定，LLM 只填 context/objective | 通常自动确认或轻量确认 |
| LLM-generated DAG | 全新场景，由 LLM 生成结构 | 必须用户确认 |
| Post-task DAG | 主任务完成后触发，如 Diff Extraction | 通常 auto_approve |

## 3. TaskDAG 模型

```text
TaskDAG
  dag_id
  task_id
  template_name
  version
  nodes[]
  edges[]
  status
  created_by

DAGNode
  node_id
  agent_slot
  intent
  task_objective
  context_slice_keys[]
  output_schema
  allowed_tools[]
  depends_on[]
  retry_policy
  timeout_seconds
```

## 4. DAGValidator

执行前必须校验：

1. 无环。
2. 所有节点引用的 Slot 已注册。
3. 节点 context_slice 满足 SlotContract。
4. 边指向合法节点。
5. 无孤岛节点。
6. ToolPolicy 与节点 allowed_tools 不冲突。
7. 输出 schema 已注册。

校验失败规则：

- Template DAG 失败：系统 bug，直接阻断并报警。
- LLM-generated DAG 失败：带错误重试一次；再次失败则请求用户或开发者介入。

## 5. Plan-then-Execute

```text
DAG 草案生成
  -> Validator 通过
  -> 发出 dag.plan.proposed 事件
  -> 前端展示 DAG 可视化
  -> 用户确认/修改/删除节点
  -> dag.plan.approved
  -> 开始执行
```

对于 `prd`、`manual` 这类确定性任务可 auto approve，但仍应该把 DAG 计划通过 SSE 发给前端，让用户知道系统将如何协作。

## 6. 执行状态机

```text
pending
  -> ready
  -> running
  -> succeeded
  -> failed
  -> blocked
  -> skipped
  -> stale
```

节点进入 `stale` 的典型场景：用户 Takeover 修改了该节点依赖的 Blackboard 字段，或上游节点重跑后输出发生变化。

## 7. 暂停与恢复

DAG 只能在节点边界安全暂停：

1. 用户发起 interrupt/takeover。
2. 正在运行的节点允许完成当前 LLM 调用，但结果暂不 merge。
3. Blackboard 标记 frozen。
4. 用户修改未执行节点参数或注入事实。
5. DirtyPropagation 标记 stale nodes。
6. 解除 frozen 并恢复 DAG。

## 8. 后置 DAG

Diff Extraction 是后置 DAG，不属于主任务 DAG。

```yaml
template_name: diff_extraction
trigger: POST_TASK_FINAL_SAVE
auto_approve: true
required_slots:
  - Diff_Extractor
edges:
  - START -> Diff_Extractor
  - Diff_Extractor -> END
```

后置 DAG 失败不改变主任务交付状态，只产生 `diff.extraction.failed` 事件和可重试记录。
