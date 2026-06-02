# Agent 协作架构

当前 EvoLoop 通过一组固定角色协作文档任务：`PM`、`Tech`、`QA`、`Reviewer`、`Writer`。这些角色都运行在同一个 `TaskContext` 上，由 `WorkflowEngine` 按任务定义调度。

## 角色分工

| 角色 | 当前职责 |
|---|---|
| PM | 起草任务目标、方案或文档主线 |
| Tech | 检查技术事实、可行性和风险 |
| QA | 检查异常流、边界条件和可执行性 |
| Reviewer | 执行门禁判断，决定通过、回环或等待裁决 |
| Writer | 汇总上下文，生成最终 Markdown 文档 |

## 共享上下文

所有角色都共享同一个 `TaskContext`，核心字段包括：

- `goal`
- `title`
- `source_materials`
- `knowledge_context`
- `round_history`
- `user_decisions`
- `gate_results`
- `artifacts`
- `step_outputs`

这样可以保证：

- 所有角色基于同一事实基线工作
- 用户裁决能直接进入后续步骤
- 前端能回放任务讨论历史和门禁结果

## 当前任务差异

### `prd`

`prd` 任务的角色协作最完整，步骤包括：

```text
PM 起草
  -> Tech / QA 并行评审
  -> PM 输出初稿
  -> Tech / QA 二审
  -> convergence_gate 判断是否收敛
  -> 需要时进入 arbitration
  -> Reviewer 门禁
  -> Writer 产出最终 PRD
```

如果 `convergence_gate` 判定未收敛，会发生两种情况：

- 还没达到最大轮次：回到 `pm_first_draft` 继续修改
- 已达到最大轮次：发出 `arbitration.requested`，等待用户裁决

### `manual`

`manual` 任务当前更偏文档生产流：

```text
ingest_materials
  -> build_context
  -> retrieve_knowledge
  -> PM 提纲
  -> Tech / QA 并行校验
  -> Reviewer 方案门禁
  -> Writer 生成概览与场景文档
  -> Reviewer 文档门禁
  -> 写入操作手册 artifact
```

## 用户裁决如何进入协作

当任务需要用户决定时：

1. `WorkflowEngine` 把任务状态设为 `waiting_for_user`
2. 事件流输出 `arbitration.requested`
3. 前端提交 `POST /api/tasks/{task_id}/decisions`
4. 后端把决策写入 `TaskContext.user_decisions`
5. 事件流输出 `arbitration.applied`
6. 引擎从 `resume_step_id` 继续执行

如果用户在提交时附带引用内容，这些内容会记录到 `UserDecision.quoted_selections`。

## 当前状态模型

任务状态：

- `created`
- `running`
- `waiting_for_user`
- `completed`
- `failed`
- `cancelled`
- `blocked`

步骤状态：

- `succeeded`
- `failed`
- `blocked`
- `needs_arbitration`
- `cancelled`

## 当前边界

- 角色本身不直接读写文件。
- 角色发言通过事件流暴露给前端。
- Writer 负责生成文档内容，但真正持久化由 artifact 步骤完成。
- 仲裁、文档保存、知识检索都通过统一的服务层和 API 进入，不在角色内部绕过。
