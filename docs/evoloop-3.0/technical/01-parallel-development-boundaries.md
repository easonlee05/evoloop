# 01 并行开发边界规范

## 1. 目标

本规范用于在 Evoloop 3.0 重构过程中提高 AI 并行开发速度，同时严格限制代码污染、语义漂移和集成回滚成本。

并行开发的首要原则不是“多开几个 agent”，而是：

```text
freeze contracts
  -> define exclusive write boundaries
  -> implement in isolated lanes
  -> integrate serially
```

也就是说：

- 并行单位必须是独占写边界，而不是模糊功能点
- 共享契约必须先冻结
- 合并必须串行收口

## 2. 总原则

### 2.1 单写者原则

同一时间，同一个文件只能有一个 lane owner。

禁止多个 agent 同时修改：

- 同一个 core schema 文件
- 同一个 workflow/runtime 入口文件
- 同一个共享测试文件
- 同一个架构入口文档

### 2.2 契约优先

只有在共享对象冻结后，才允许多 lane 并行。

共享对象包括：

- `WorkItem`
- `Playbook`
- `ProductContext`
- `DecisionGate`
- `ArtifactGraph`
- `WorkerAdapter`
- 核心 artifact 命名：`machine_spec`、`human_brief`、`optional_prd`

额外强约束：

- `machine_spec` 是唯一 source of truth
- `optional_prd` / `optional_manual` 只能作为 projection
- `review_result` 必须可追溯回 `machine_spec`

### 2.3 worktree 隔离

每个并行 agent 必须使用独立 worktree / branch。

禁止多个 agent 在同一工作目录直接写同一份文件。

### 2.4 集成串行

并行实现可以，但最终合并、回归测试、入口收口必须由单一 integrator 执行。

### 2.5 测试隔离

每个 lane 优先新增自己的测试文件，不共写一个大回归测试文件。

## 3. 角色划分

### 3.1 Architect / Contract Owner

唯一允许修改以下内容：

- `docs/evoloop-3.0/**`
- 共享对象命名
- 核心 schema
- lane 切分边界

职责：

- 冻结契约
- 发布 lane 范围
- 审核跨 lane 影响

### 3.2 Worker Lane Owner

只允许在自己独占边界内实现。

职责：

- 完成本 lane 代码和测试
- 不越权修改共享入口
- 明确列出受影响契约和未完成项

### 3.3 Integrator

唯一负责：

- 收敛共享入口
- 跑回归测试
- 串行合并 lane
- 解决边界冲突

## 4. 禁止并行修改的高污染区域

以下文件或区域默认禁止多 lane 同时修改：

- `app/workflows/engine.py`
- `app/core/task.py`
- `app/core/context.py`
- `app/api/server.py`
- `AGENTS.md`
- `AGENT_MAP.md`
- `docs/evoloop-3.0/architecture/00-global-architecture.md`
- `docs/evoloop-3.0/technical/00-evolution-roadmap.md`
- 共享测试入口：`tests/test_backend_phase1.py`

这些文件只能由 Architect 或 Integrator 在收口阶段修改。

## 5. 当前推荐 lane 切分

### Lane A：3.0 Contracts

目标：

- 定义和演进 3.0 核心对象

可写范围：

- `app/core/work.py`
- `app/core/playbook.py`
- `app/core/artifact_graph.py`
- `app/core/review.py`
- `docs/evoloop-3.0/**`

Lane A 冻结交付物：

- `WorkItem`
- `Playbook`
- `ProductContext`
- `DecisionGate`
- `ArtifactGraph`
- `WorkerAdapter`
- `ReviewResult`
- `machine_spec` source-of-truth 约束

禁止修改：

- `app/workflows/engine.py`
- `app/services/task_service.py`
- legacy workflow 文件

### Lane B：Legacy Bridge

目标：

- 把 1.0 能力包进 3.0 facade

可写范围：

- `app/services/task_service.py`
- `app/workflows/definitions.py`
- `app/workflows/manual.py`
- `app/workflows/prd.py`

禁止修改：

- 3.0 core schema 文件
- MCP / CLI adapter

### Lane C：Spec-to-Agent

目标：

- 实现首个 native 3.0 playbook

可写范围：

- `app/workflows/spec_to_agent.py`
- `tests/test_spec_to_agent.py`

禁止修改：

- legacy workflow 文件
- `app/workflows/engine.py`
- `app/api/server.py`

### Lane D：CLI Adapter

目标：

- 本地终端调用入口

可写范围：

- `app/cli/**`
- `tests/test_cli_*.py`

禁止修改：

- runtime
- shared schema
- legacy bridge

### Lane F：Runtime & Context Optimization

目标：

- 实现 Sticky Latch 提示词锁定和 L1/L2 多级上下文压缩与复水，优化 Token 费用与 Prompt Caching 命中率。

可写范围：

- `app/services/llm.py`
- `app/workflows/engine.py` (对 LLM 传输部分的微调优化)
- `tests/test_runtime_optimization.py`

禁止修改：

- CLI
- MCP
- 3.0 core schema
- legacy bridge

### Lane E：Acceptance Review

目标：

- 第二个 native 3.0 playbook

可写范围：

- `app/workflows/acceptance_review.py`
- `tests/test_acceptance_review.py`

禁止修改：

- CLI
- MCP
- shared runtime

## 6. 推荐并行顺序

### Wave 0：串行冻结

必须串行完成：

- 3.0 核心对象定义
- artifact 命名与职责
- lane 切分

### Wave 1：低污染并行

推荐只开以下 lane：

- Lane A：3.0 Contracts
- Lane B：Legacy Bridge
- Lane C：Spec-to-Agent

原因：

- 共享边界最清晰
- 最接近 3.0 主价值
- 污染风险最低

### Wave 2：收口与回归

由 Integrator 执行：

- 合并 Wave 1
- 修共享入口
- 跑测试
- 处理 artifact 命名与接口一致性

### Wave 3：第二轮并行

在 Wave 1 稳定后再开放：

- Lane D：CLI Adapter
- Lane E：Acceptance Review

### Wave 4：后期扩展

最后再考虑：

- MCP Adapter
- runtime replacement
- learning loop / GBrain

## 7. 提交流水要求

每个 lane 提交时必须附带：

- 变更文件列表
- 受影响契约列表
- 本 lane 测试结果
- 未完成项 / 风险项

不允许只提交“代码改完了”这种模糊说明。

## 8. 冲突判定规则

### 必须停止并升级给 Architect / Integrator

出现以下情况必须停止本 lane，并请求收口决策：

- 需要改共享 schema
- 需要改共享入口文件
- 发现另一个 lane 正在写同一批文件
- 发现 artifact 命名与 contract 不一致
- 发现需要扩大 lane 边界

### 可在本 lane 内自行处理

- 自己负责目录下的新文件
- 自己测试文件内的断言变更
- 自己 playbook 内部实现细节

## 9. 为什么不按功能点随意拆

错误拆法：

- 一个 lane 做“PRD 改造”
- 一个 lane 做“文档优化”
- 一个 lane 做“spec 生成”

这种拆法会同时碰：

- shared context
- workflow engine
- artifact policy
- API output

结果通常是高污染和高返工。

正确拆法应按独占写边界拆：

- core contracts
- legacy bridge
- native playbook
- adapter
- review

## 10. 与 3.0 技术路线的关系

本规范服务于 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`，并与其中阶段保持一致：

- 先冻结 3.0 contracts
- 再包裹 1.0
- 再做 native 3.0 playbook
- 再做 adapter
- 最后再换 runtime

并行开发必须服从这个顺序，不能跳过前置边界冻结阶段。
