# 09 平台 API 与事件架构

## 1. API 是平台外观层

API 层的职责不是暴露内部文件结构，而是把平台能力组织成稳定的产品接口。它需要同时承载：

- Workspace 管理
- Task 与 DAG 控制
- Artifact 与终稿保存
- Evidence 与 Diff 学习
- Rule 审核与入库
- SSE 事件回放与直播

## 2. API 分组

### 2.1 Workspace API

管理运行环境和领域配置：

```text
POST /api/workspaces
GET  /api/workspaces/{workspace_id}
PUT  /api/workspaces/{workspace_id}/domain-pack
GET  /api/workspaces/{workspace_id}/runtime-profile
```

### 2.2 Task API

管理任务生命周期：

```text
POST /api/tasks
GET  /api/tasks
GET  /api/tasks/{task_id}
POST /api/tasks/{task_id}/plan
POST /api/tasks/{task_id}/plan/approve
POST /api/tasks/{task_id}/run
POST /api/tasks/{task_id}/interrupt
POST /api/tasks/{task_id}/takeover
POST /api/tasks/{task_id}/decisions
```

### 2.3 Artifact API

管理交付文档：

```text
GET  /api/tasks/{task_id}/document
PUT  /api/tasks/{task_id}/document
POST /api/tasks/{task_id}/save-final
GET  /api/tasks/{task_id}/artifacts
GET  /api/artifacts/{artifact_id}
```

### 2.4 Evidence / Diff / Rule API

```text
GET  /api/tasks/{task_id}/evidence
GET  /api/diff/tasks/{task_id}/candidates
POST /api/diff/tasks/{task_id}/retry
GET  /api/rules/candidates
POST /api/rules/candidates/{rule_id}/review
GET  /api/rules/approved
POST /api/rules/{rule_id}/archive
```

## 3. API 语义原则

### 3.1 文档保存不等于终稿保存

普通 `PUT /document` 不触发学习；只有 `save-final` 才触发 Evidence 和 Diff。

### 3.2 Review API 面向 CandidateRule

v2 中建议把审核动作统一到 CandidateRule review API，而不是继续沿用“直接 approve 某条规则 id”的扁平接口。

### 3.3 API 返回结构化状态

接口应返回：

- 明确状态枚举
- 资源 ID
- 事件关联 ID
- 是否进入 waiting/degraded/retryable

而不是依赖前端从文案里猜测状态。

## 4. SSE 架构

SSE 是用户可观察性的主通道。事件至少分三层：

### 4.1 控制面事件

- `dag.plan.proposed`
- `dag.plan.approved`
- `dag.node.started`
- `dag.node.completed`
- `arbitration.requested`
- `task.waiting_for_user`

### 4.2 数据面事件

- `artifact.created`
- `artifact.final_saved`
- `evidence.frozen`
- `diff.candidates_ready`
- `rule.stored`

### 4.3 诊断面事件

- `tool.call.denied`
- `knowledge.degraded`
- `budget.exhausted`
- `rule.store.failed`

## 5. 事件模型

```text
Event
  id
  task_id
  workspace_id
  type
  role
  status
  payload
  created_at
```

事件 payload 必须遵守安全约束：

- 不含绝对路径
- 不含密钥
- 不含完整 prompt
- 不含未授权材料全文

## 6. Event Replay

事件流应分两段：

1. 历史回放：从 `events.jsonl` 读取。
2. 实时直播：连接 Event Bus。

刷新页面时：

```text
load task current state
  -> replay persisted events
  -> subscribe to live stream
```

## 7. API 与运行时解耦

API 层不应该直接实现 Agent 逻辑，它只负责：

- 参数验证
- 鉴权与租户边界
- 调用平台服务
- 序列化结果与事件

所有运行时动作，如 DAG 校验、节点调度、规则冲突检测，都应落在对应服务与运行时组件中。

## 8. 兼容策略

当前已有 Phase 1 API，可以逐步迁移：

- 保留原有 `/api/tasks`, `/api/tasks/{id}/run`, `/api/tasks/{id}/document`
- 新增 `plan`, `save-final`, `takeover`, `candidate review`
- 前端逐步切换到新事件和新资源模型

这样可以避免一次性破坏现有工作台。
