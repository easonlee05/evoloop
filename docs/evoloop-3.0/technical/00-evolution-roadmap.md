# 00 1.0 到 3.0 技术演进路线

## 1. 迁移总原则

Evoloop 不走 `1.0 -> 2.0 -> 3.0` 顺序升级。

正确路线是：

```text
freeze 3.0 contracts
  -> wrap 1.0 with legacy bridge
  -> add native 3.0 playbooks
  -> replace runtime incrementally
  -> add adapters
  -> add learning loop later
```

也就是说：

- 3.0 先定义边界，不先补完 2.0。
- 2.0 只复用仍然成立的抽象。
- 1.0 先被包进新边界，而不是立刻彻底重写。

## 2. 当前代码的现实基线

现有代码更接近 1.0 / Phase 1：

- `app/core/task.py`：`TaskDefinition`、`WorkflowSpec`、`StepResult`
- `app/core/context.py`：`TaskContext`
- `app/workflows/engine.py`：线性工作流引擎
- `app/workflows/manual.py` / `prd.py`：legacy 产品线定义
- `app/services/task_service.py`：任务创建和运行
- `app/services/tool_service.py`：Tool 调用和权限审计

这些模块不应该被立即抛弃，而应先充当 3.0 过渡期的基础设施。

## 3. 先冻结的 3.0 协议

在真正动大代码前，必须先冻结这些 3.0 概念：

- `WorkItem`
- `Playbook`
- `ProductContext`
- `DecisionGate`
- `ArtifactGraph`
- `WorkerAdapter`
- `ReviewResult`

这一阶段的目标不是全部实现，而是确保后续重构不会围绕 2.0 的旧中心反复返工。

当前冻结模块：

- `app/core/work.py`
- `app/core/playbook.py`
- `app/core/artifact_graph.py`
- `app/core/review.py`

当前冻结原则：

- `machine_spec` 是唯一 source of truth
- `human_brief` / `optional_prd` / `optional_manual` 都是 projection 或 optional artifact
- 本阶段不实现 MCP、CLI 或 legacy workflow 重写

## 4. Phase 0：文档和路由对齐

### 目标

让 3.0 成为后续模型、开发者和实现工作的默认真相源。

### 工作项

- 建立 `docs/evoloop-3.0/`
- 在 `AGENTS.md` 中把 3.0 文档加入首读规则
- 在 `AGENT_MAP.md` 中把 3.0 设为默认架构入口
- 在 2.0 入口文档中明确标记“仅作历史参考”

### 完成标准

- 新对话中的 AI 工具优先读 3.0 文档
- 2.0 文档不再被误认为当前实现目标

## 5. Phase 1：Legacy Bridge

### 目标

让 1.0 能力先跑在 3.0 的新边界之内。

### 做法

在不大规模改写业务逻辑的前提下，引入一层桥接：

```text
WorkItem facade
  -> legacy playbook adapter
  -> existing WorkflowEngine
  -> existing TaskContext / ToolService / Artifact flow
```

### 推荐改动方向

- `TaskDefinition` 继续保留，但外部逐步改叫 `legacy playbook`
- `TaskContext` 继续保留，但通过 facade 对外映射到 `ProductContext`
- `manual` / `prd` 改以 `legacy_manual` / `legacy_prd` 视角被消费
- `machine_spec` 作为统一锚点进入 `ArtifactGraph`

### 不要做

- 不要先做完整 DAG runtime
- 不要先重写所有 manual/prd 逻辑
- 不要在这一阶段引入 MCP

### 完成标准

- 外部入口能创建统一的 3.0 `WorkItem`
- `manual` / `prd` 仍然可跑，但已不再直接暴露 1.0 语义

## 6. Phase 2：Native 3.0 Playbook MVP

### 目标

做出第一个真正代表 3.0 方向的原生能力。

### 首选 Playbook

`spec_to_agent`

### 最小链路

```text
input
  -> normalize context
  -> identify open questions
  -> human decision gates
  -> compile machine spec
  -> generate agent package
  -> generate acceptance protocol
```

### 推荐输出

- `machine_spec.yaml`
- `human_brief.md`
- `agent_package_codex.md`
- `acceptance.md`
- `review_checklist.md`
- `traceability.json`

默认策略：

- 必产出 `machine_spec.yaml`
- 推荐同时产出 `human_brief.md`
- `PRD.md` 和 `manual` 视场景按需渲染，不再默认充当真相源
- 输出之间的关系必须写入 `ArtifactGraph`，并以 `machine_spec` 为锚点

### 关键原因

这是 3.0 的北极星能力，比补齐 `manual/prd` 或 Diff 学习更接近未来产品价值。

### 完成标准

- 项目能把一句需求转成 AI worker 可执行任务包
- 这条链路不依赖 PRD / manual 才能成立

## 7. Phase 3：ArtifactGraph 与 Review 骨架

### 目标

从“会生成任务包”升级到“知道这些产物之间的关系”。

### 工作项

- 建立轻量 `ArtifactGraph`
- 建立 requirement / decision / acceptance / task 的基础映射
- 为后续 review 和 change impact 提供结构基础
- 建立 `ReviewResult` 最小 schema，但不在本阶段接 API/runtime

### 最小节点类型

- `requirement`
- `decision`
- `machine_spec`
- `agent_package`
- `acceptance_protocol`
- `review_result`

### 完成标准

- 系统可以回答“这个 agent package 对应哪些 requirement 和 decision”

## 8. Phase 4：CLI Adapter

### 目标

先用 CLI 验证数字产品经理到数字开发人员的协作链路。

### 推荐命令

```text
evoloop compile
evoloop package
evoloop acceptance
evoloop review
```

### 原因

- CLI 更轻
- 更适合本地开发调试
- 更适合先验证与 Codex 的协作方式

### 完成标准

- 本地可以在终端里生成 agent package 并回收 review

## 9. Phase 5：MCP Adapter MVP

### 目标

让 Codex / Claude Code 能通过标准协议获取数字 PM 能力。

### 第一版只做这些能力

- `get_project_context`
- `create_requirement`
- `compile_spec`
- `get_agent_package`
- `request_decision`
- `get_acceptance`

### 不要做

- 不要在第一版做复杂自动执行
- 不要让 MCP 直接定义内核模型
- 不要把 MCP server 做成“几个文档查询工具”的空壳

### 完成标准

- 外部 AI worker 可以通过 MCP 获取上下文、任务包和裁决结果

## 10. Phase 6：Acceptance Review Native 化

### 目标

让 Evoloop 不只“派活”，还能“验收数字开发人员的工作”。

### Playbook

`acceptance_review`

### 输入

- `machine_spec`
- `acceptance_protocol`
- `implementation summary`
- `diff` 或文件变更摘要

### 输出

- `review_result.md`
- `requirement_coverage.json`
- `fix_tasks.md`

### 完成标准

- 系统能指出哪些 requirement 没被覆盖、哪些 acceptance 没满足

## 11. Phase 7：Runtime Replacement

### 目标

在 3.0 主链路成立后，再把底层执行内核升级为更通用的 runtime。

### 2.0 中可直接吸收的部分

- `TaskDAG`
- `DAGValidator`
- `Blackboard`
- `ContextSlicer`
- `MergeEngine`
- `Checkpoint`
- `Plan-then-Execute`

### 迁移方式

```text
WorkflowStep[]
  -> linear PlaybookGraph
  -> partial DAG
  -> full Playbook runtime
```

### 原则

- 保持 API facade 尽量稳定
- 不要求前端立刻感知内部 runtime 切换
- 先兼容 legacy playbook，再迁 native 3.0 playbook

### 完成标准

- legacy 与 native playbook 都能跑在统一 runtime 上

## 12. Phase 8：Learning Loop 与 GBrain

### 目标

在主链路稳定后，再建设长期学习与知识治理。

### 3.0 中的学习重点

不再只比较“AI 草稿 vs 用户终稿”，而要学习：

- 哪些 requirement 容易被 AI 误解
- 哪些 decision 应该更早暴露
- 哪些 acceptance 写得不够可测试
- 哪些 agent package 模板最稳定

### GBrain 的定位

继续作为长期知识基础设施，而不是运行时黑板。

### 完成标准

- review finding 和 evidence 能进入长期知识循环
- 但学习失败不影响主任务交付

## 13. 推荐的模块落点

### 近期新增

- `app/core/work.py`
- `app/core/playbook.py`
- `app/core/artifact_graph.py`
- `app/services/playbook_service.py`
- `app/services/worker_adapter_service.py`
- `app/workflows/spec_to_agent.py`
- `app/workflows/acceptance_review.py`

### 过渡保留

- `app/core/task.py`
- `app/core/context.py`
- `app/workflows/engine.py`
- `app/workflows/manual.py`
- `app/workflows/prd.py`

### 中期重构

- `app/core/dag.py`
- `app/core/blackboard.py`
- `app/core/context_slicer.py`
- `app/core/merge_engine.py`
- `app/mcp/`
- `app/cli/`

## 14. 每阶段的判断标准

### 应继续推进

- 新能力已经围绕 3.0 的对象模型落地
- 旧能力只是被包裹，而不是继续主导平台边界
- 下游 AI worker 协作链路越来越短

### 应暂停纠偏

- 实现仍以 `manual/prd` 为中心
- 代码在为了补完整 2.0 而绕远路
- MCP / CLI 在定义内核而不是消费内核
- 新增模块又回到“写文档平台”的语义
