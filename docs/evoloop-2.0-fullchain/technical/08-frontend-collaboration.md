# 08 前端共创

## 1. 前端角色

前端不是日志显示器，而是 Evoloop 的共创控制台。它要让用户理解 AI 如何工作，并在关键点介入。

核心页面：

| 页面 | 能力 |
|---|---|
| Landing / Task Create | 创建任务、选择目标、上传材料。 |
| Workspace | DAG 透视窗、消息流、文档编辑、暂停/恢复/接管。 |
| Task Hall | 任务状态、历史、继续执行。 |
| Knowledge Base | 安全摘要、知识健康、候选知识。 |
| Rule Audit | 候选法则审核、修改后入库、限定作用域、驳回。 |
| Domain Pack Onboarding | Workspace 初始化、领域包和扩展包选择。 |

## 2. 工作流透视窗

前端通过 SSE 渲染：

- DAG 节点状态。
- Agent 消息摘要。
- Tool 调用状态。
- 知识降级提示。
- 仲裁请求。
- 终稿保存和 Diff 学习状态。

前端不得解析 Python 日志或 prompt；所有展示都来自结构化事件。

## 3. 用户打断与接管

```text
User clicks Pause
  -> POST /api/tasks/{id}/interrupt
  -> task.interrupt.requested
  -> DAG pauses at node boundary
  -> user edits pending node params or injects facts
  -> POST /api/tasks/{id}/takeover
  -> blackboard fields updated by Orchestrator
  -> stale nodes computed
  -> resume
```

接管不是“继续聊天”，而是把用户明确事实写入 Blackboard，并让下游节点重跑。

## 4. 文档编辑

编辑器区分两类保存：

| 保存类型 | API | 是否触发 Diff |
|---|---|---|
| 自动保存 / 草稿保存 | `PUT /api/tasks/{id}/document` | 否 |
| 保存终稿 / 完成交付 | `POST /api/tasks/{id}/save-final` | 是 |

终稿保存后，前端应展示“正在提炼可复用经验”，并在 `diff.candidates_ready` 后引导用户进入 Rule Audit。

## 5. 法则审核 UX

CandidateRule 卡片应展示：

- 法则标题和内容。
- 来源任务和证据摘要。
- AI 原文 vs 用户终稿差异摘要。
- 建议 scope/protection/confidence。
- 冲突/重复提示。
- 操作：通过、修改后入库、限定作用域入库、驳回。

有冲突的候选不能一键静默入库；必须展示冲突细节并让用户确认。

## 6. 前端状态不做来源真相

前端可以缓存消息和文档，但来源真相始终在后端：

- 任务状态来自 `/api/tasks/{id}`。
- 文档内容来自 Artifact API。
- DAG 状态来自 DAG run API 或事件回放。
- 法则状态来自 RuleService API。
