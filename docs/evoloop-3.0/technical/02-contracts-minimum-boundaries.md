# 02 3.0 Contracts 最小冻结边界

## 1. 目标

本文件用于冻结 Evoloop 3.0 的最小共享协议，作为并行 lane 的实现边界。

本阶段只冻结：

- 对象命名
- 最小字段集合
- source-of-truth 约束
- lane 间禁止越权的规则

本阶段明确不做：

- 不实现 MCP adapter
- 不实现 CLI adapter
- 不替换 runtime
- 不改 legacy workflow 业务逻辑

## 2. 冻结模块落点

Lane A / 3.0 Contracts 独占维护以下文件：

- `app/core/work.py`
- `app/core/playbook.py`
- `app/core/artifact_graph.py`
- `app/core/review.py`

这些文件只表达共享 schema 和序列化边界，不表达 runtime 逻辑。

## 3. machine_spec 是唯一真相源

从 3.0 contracts 冻结版本起：

- `machine_spec` 是唯一 source of truth
- `human_brief`、`optional_prd`、`optional_manual` 都只能是 projection
- `agent_package`、`acceptance_protocol`、`review_result` 必须可追溯回 `machine_spec`
- 任何 lane 都不能把 `optional_prd`、`optional_manual` 或 worker 输出结果提升为新的真相源

因此：

- 编译链路以 `machine_spec` 为中心
- review 链路以 `machine_spec + acceptance_protocol` 为中心
- traceability 必须以 `machine_spec` 节点为锚点建立

### 3.1 代码级强制约束校验

为了防止任何 runtime 逻辑或 lane 越权修改真相源关系，我们已在 `ArtifactGraph.validate()` 中实现了如下强校验逻辑：

1. **唯一真相源校验 (Single Source of Truth)**：
   - 只要图中包含任何投影（`human_brief`, `optional_prd`, `optional_manual`）或派生资产（`agent_package`, `acceptance_protocol`, `review_result`, `review_checklist`, `traceability_map`），图中**必须存在且仅存在一个**类型为 `ArtifactNodeType.MACHINE_SPEC` 的节点。
2. **可追溯性校验 (Traceability)**：
   - 每一个投影或派生资产节点，都必须通过关系边与 `machine_spec` 保持连通（无向连通分量一致），图上不允许存在任何脱离真相源的孤立派生/投影节点。
3. **禁止反向依赖 (No Reverse Dependency)**：
   - 严禁 `machine_spec` 本身通过 `derives_from` 关系反向指向并依赖于任何投影或派生物节点（即真相源不能由投影/派生节点生成）。

任何不满足以上三条规则的交付物关系图，都将抛出 `ArtifactGraphValidationError` 异常，从而从运行时根源杜绝非法状态。

## 4. 冻结对象

## 4.1 WorkItem

模块：`app/core/work.py`

最小职责：

- 表达统一工作单元身份
- 关联 `ProductContext` 与 `ArtifactGraph`
- 表达高层状态
- 不承载 engine 内部执行细节

最小字段：

- `work_id`
- `work_type`
- `playbook_id`
- `title`
- `objective`
- `workspace_id`
- `status`
- `product_context_ref`
- `artifact_graph_ref`
- `current_decision_gate_id`
- `created_at`
- `updated_at`
- `metadata`

## 4.2 Playbook

模块：`app/core/playbook.py`

最小职责：

- 定义数字产品经理工作套路
- 表达步骤边界、允许工具和产物类型
- 不实现 WorkflowEngine 或 DAG runtime

最小字段：

- `playbook_id`
- `version`
- `trigger_types`
- `steps`
- `decision_gate_ids`
- `allowed_tools`
- `output_artifact_types`
- `metadata`

### PlaybookStep

最小字段：

- `step_id`
- `title`
- `purpose`
- `allowed_tools`
- `produces_artifact_types`
- `next_step_ids`
- `metadata`

## 4.3 ProductContext

模块：`app/core/playbook.py`

最小职责：

- 表达跨轮次稳定产品真相
- 收敛需求、约束、假设、用户裁决、知识引用和 worker 反馈
- 不直接替代运行时 `TaskContext`

最小字段：

- `objective`
- `source_inputs`
- `requirements`
- `constraints`
- `assumptions`
- `user_decisions`
- `knowledge_refs`
- `worker_feedback`
- `metadata`

## 4.4 DecisionGate

模块：`app/core/playbook.py`

最小职责：

- 暴露必须由人类裁决的问题
- 明确选项、影响与 resolution
- 不允许 AI 静默脑补取舍

最小字段：

- `gate_id`
- `work_id`
- `question`
- `options`
- `impact_summary`
- `blocking`
- `status`
- `resolution`
- `metadata`

## 4.5 ArtifactGraph

模块：`app/core/artifact_graph.py`

最小职责：

- 表达产物节点和关系边
- 保持 `machine_spec` 节点为图中的真相锚点
- 为 review / traceability / impact analysis 提供关系骨架
- 不实现持久化引擎或复杂查询服务

最小节点类型：

- `requirement`
- `decision`
- `human_brief`
- `machine_spec`
- `agent_package`
- `acceptance_protocol`
- `review_checklist`
- `review_result`
- `traceability_map`
- `decision_log`
- `optional_prd`
- `optional_manual`

最小边类型：

- `derives_from`
- `addresses_requirement`
- `resolves_decision`
- `validates`
- `reviews`
- `supersedes`

## 4.6 WorkerAdapter

模块：`app/core/playbook.py`

最小职责：

- 定义与下游 worker 的统一对接合同
- 表达 package format、invocation policy、result intake policy
- 不实现具体 MCP / CLI / web 调用

最小字段：

- `adapter_id`
- `target_type`
- `package_format`
- `invocation_policy`
- `result_intake_policy`
- `metadata`

## 4.7 ReviewResult

模块：`app/core/review.py`

最小职责：

- 表达验收评审结论
- 记录 requirement coverage、issues、fix tasks
- 保证 review 直接挂接 `machine_spec`

最小字段：

- `review_id`
- `work_id`
- `machine_spec_ref`
- `acceptance_protocol_ref`
- `verdict`
- `summary`
- `coverage`
- `issues`
- `fix_tasks`
- `created_at`
- `metadata`

## 5. 对其他 lane 的硬约束

## 5.1 Lane B / Legacy Bridge

- 可以把 `TaskDefinition` / `TaskContext` 映射到 3.0 facade
- 不得扩展或改名冻结字段
- 不得让 legacy manual/prd 反向成为 source of truth

## 5.2 Lane C / Spec-to-Agent

- 必须生成 `machine_spec`
- 生成的 `human_brief`、`agent_package`、`acceptance_protocol` 必须能追溯到 `machine_spec`
- 不得引入第二套平行 spec schema

## 5.3 Lane D / CLI Adapter

- 只能消费已冻结对象
- 不得在 CLI 层新定义核心业务 schema

## 5.4 Lane E / Acceptance Review

- 必须以 `machine_spec + acceptance_protocol` 作为 review 输入核心
- `review_result` 必须回写到 `ArtifactGraph`
- 不得以 `optional_prd` 或 `optional_manual` 作为 review 主依据

## 6. 当前未完成项

这些内容有意留给后续 lane / 收口阶段：

- `TaskContext <-> ProductContext` 的正式 bridge
- `WorkItem` 对 `TaskService` 的 facade 接线
- native `spec_to_agent` playbook 实现
- native `acceptance_review` playbook 实现
- `WorkerAdapter` 的 CLI / MCP 具体实现
- `ArtifactGraph` 的存储、查询与变更影响分析能力
- `ReviewResult` 与 API / SSE surface 的集成
