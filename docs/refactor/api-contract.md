# API / SSE Contract for EvoLoop

本文档描述当前前端工作台和后端服务之间的实际契约。前端只消费这里定义的 HTTP API、Artifact 资源和结构化 SSE 事件，不解析后端日志文本。

## Contract Principles

- 当前任务类型只有 `manual` 和 `prd`。
- 所有任务都通过 `TaskDefinition` 创建，并由 `WorkflowEngine` 执行。
- 前端通过 SSE 消费结构化事件，不读取 console 标记。
- 事件 payload 不包含凭证、完整本地路径、未授权材料原文或 `.env` 内容。
- Tool 权限不足返回 `tool.call.denied`。
- 用户裁决是正常流程：`arbitration.requested` 后任务暂停，`arbitration.applied` 后从 `resume_step_id` 恢复。

## Common Objects

### Event

```json
{
  "id": "evt_000012",
  "task_id": "task_abc123",
  "type": "workflow.step.completed",
  "role": "PM",
  "status": "succeeded",
  "payload": {
    "step_id": "pm_draft",
    "summary": "PM completed"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### Artifact

```json
{
  "artifact_id": "artifact_task_abc123_001",
  "task_id": "task_abc123",
  "name": "PRD.md",
  "version": 1,
  "content_type": "text/markdown",
  "created_by": "Writer",
  "summary": "Generated PRD.md"
}
```

## Endpoints

### `POST /api/tasks`

创建任务。前端可以只传 `{ "prompt": "..." }`；后端会自动推断任务类型，并补全默认 `username`。

常见请求字段：

| Field | Type | Required | Notes |
|---|---|---:|---|
| `type` | string | no | `manual` 或 `prd`；缺省时按 prompt 推断 |
| `username` | string | no | 未传时默认 `frontend` |
| `title` | string | no | 前端显示标题 |
| `goal` | string | no | 通用任务目标 |
| `feature` | string | no | `prd` 任务名称 |
| `business_goal` | string | no | `prd` 任务业务目标 |
| `module_name` | string | no | `manual` 模块名 |
| `material_ids` | string[] | no | 上传材料 id |

Response:

```json
{
  "task_id": "task_abc123",
  "taskId": "task_abc123",
  "id": "task_abc123",
  "status": "created"
}
```

### `GET /api/tasks`

返回任务大厅列表。`status` 是前端展示态，`raw_status` 是后端原始状态。

```json
{
  "tasks": [
    {
      "id": "task_abc123",
      "task_id": "task_abc123",
      "title": "积分防刷网关",
      "type": "prd",
      "status": "running",
      "raw_status": "running",
      "agent": "PM + Tech + QA",
      "priority": "medium",
      "updated": "刚刚"
    }
  ]
}
```

### `GET /api/tasks/{task_id}`

读取单个任务的前端展示数据。

### `POST /api/tasks/{task_id}/run`

显式启动或继续任务执行。

```json
{
  "task_id": "task_abc123",
  "taskId": "task_abc123",
  "status": "running",
  "waiting_step_id": null
}
```

### `POST /api/tasks/{task_id}/interrupt`

把任务标记为取消，并输出 `task.cancelled`。

### `DELETE /api/tasks/{task_id}`

软删除任务。任务会从主列表隐藏，但仍可在回收站查看与恢复。

### `GET /api/tasks/{task_id}/events`

返回 SSE 事件流。服务会先回放已有 `events.jsonl`，随后继续推送实时事件。

SSE frame:

```text
id: evt_000012
event: workflow.step.completed
data: {"id":"evt_000012","task_id":"task_abc123","type":"workflow.step.completed","payload":{"step_id":"pm_draft"}}
```

每个 `data` 对象可能包含 `frontend_message` 字段，供工作台直接渲染消息 UI；标准事件字段仍然是主数据源。

### `GET /api/tasks/{task_id}/messages`

返回已格式化的前端消息列表，适合初始化工作台消息区。

### `POST /api/tasks/{task_id}/decisions`

提交用户裁决并恢复任务执行。

Request:

```json
{
  "decision": "选择方案 B，接受短时间缓存脏数据，但必须加入事后对账。",
  "selected_option": "B",
  "quoted_selections": [
    {
      "source_type": "message",
      "source_id": "msg_pm_001",
      "source_label": "PM Agent",
      "text": "需要优先保留审计链路"
    }
  ]
}
```

`quoted_selections` 可选，可来自会话区或文档区的已选文本。

### `GET /api/tasks/{task_id}/artifacts`

列出当前任务的 artifact。

### `GET /api/tasks/{task_id}/document`

读取当前任务最新 Markdown 文档。如果任务还没有 artifact，会返回一个占位文档内容，不会自动触发任务运行。

```json
{
  "task_id": "task_abc123",
  "taskId": "task_abc123",
  "artifact_id": "artifact_task_abc123_001",
  "artifactId": "artifact_task_abc123_001",
  "name": "PRD.md",
  "version": 1,
  "title": "积分防刷网关",
  "content": "# 积分防刷网关 PRD\n"
}
```

### `PUT /api/tasks/{task_id}/document`

保存文档内容。若已有 artifact，会先备份旧版本再更新内容。

```json
{
  "content": "# Updated PRD\n"
}
```

### `GET /api/artifacts/{artifact_id}`

读取单个 artifact，响应中可包含 Markdown 内容，但不会返回服务器本地绝对路径。

### `PUT /api/artifacts/{artifact_id}`

更新单个 artifact。行为和任务文档保存一致：先备份、再更新。

### `POST /api/materials`

上传材料文件，返回 `material_id` 和安全摘要。

```json
{
  "material_id": "material_abc123",
  "status": "uploaded",
  "summary": "source.pdf uploaded; full local path is not exposed."
}
```

### `GET /api/knowledge/health`

返回当前知识检索健康状态。

### `GET /api/knowledge`

返回知识卡片列表，只包含安全摘要。

### `POST /api/knowledge`

创建候选知识卡片数据。当前不会直接写入可信知识存储。

### `GET /api/rules?status=pending|approved|rejected`

返回规则页面使用的规则卡片列表。

### `POST /api/rules/{rule_id}/approve`

批准规则卡片，可附带编辑后的内容。

### `POST /api/rules/{rule_id}/reject`

拒绝规则卡片。

### `GET /api/recycle`

返回已软删除任务和演示回收站项。

### `POST /api/recycle/{item_id}/restore`

恢复回收站项或软删除任务。

### `DELETE /api/recycle/{item_id}`

永久删除回收站项；对任务会删除任务目录。

### `GET /api/conversations/recent`

返回左侧任务栏最近任务分组，按最后活跃时间倒序排列，不截断为固定 10 条。

## Task Request Examples

### manual

```json
{
  "type": "manual",
  "username": "alice",
  "module_name": "节点池",
  "goal": "生成节点池操作手册",
  "instructions": "重点说明扩缩容限制",
  "knowledge_scope": "cloud-native",
  "material_ids": ["material_001", "material_002"]
}
```

### prd

```json
{
  "type": "prd",
  "username": "alice",
  "feature": "积分防刷网关",
  "business_goal": "降低异常积分套利",
  "constraints": ["首期不改积分核心账务"],
  "preferences": ["优先保证可审计"],
  "material_ids": ["material_003"]
}
```

## Event Examples

### `arbitration.requested`

```json
{
  "id": "evt_000020",
  "task_id": "task_abc123",
  "type": "arbitration.requested",
  "role": "SYSTEM",
  "status": "needs_arbitration",
  "payload": {
    "step_id": "arbitration_business_tradeoff",
    "resume_step_id": "pm_after_arbitration",
    "dispute_package": {
      "title": "业务取舍需要裁决",
      "background": "定义失败补偿",
      "decision_needed": "请选择一致性、性能和交付速度之间的首期取舍。",
      "options": [
        {
          "label": "A",
          "pm_position": "同步强一致",
          "tech_position": "成本较高",
          "qa_position": "异常更少",
          "benefit": "结果确定",
          "cost": "性能成本",
          "risk": "发布慢",
          "recommended": false
        },
        {
          "label": "B",
          "pm_position": "异步加对账",
          "tech_position": "解耦更好",
          "qa_position": "需补偿机制",
          "benefit": "易交付",
          "cost": "短时不一致",
          "risk": "需审计",
          "recommended": true
        }
      ],
      "impact_after_decision": "PM 将按用户裁决重写主流程、风险和验收标准。"
    }
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### `arbitration.applied`

```json
{
  "id": "evt_000021",
  "task_id": "task_abc123",
  "type": "arbitration.applied",
  "status": "applied",
  "payload": {
    "decision": "选择方案 B，接受短时间缓存脏数据，但必须加入事后对账。",
    "selected_option": "B",
    "resume_step_id": "pm_after_arbitration"
  },
  "created_at": "2026-05-30T06:01:00+00:00"
}
```

### `workflow.step.started`

```json
{
  "id": "evt_000004",
  "task_id": "task_abc123",
  "type": "workflow.step.started",
  "role": "PM",
  "payload": {
    "step_id": "pm_draft",
    "step_type": "agent",
    "title": "PM 输出 PRD 草案"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### `artifact.created`

```json
{
  "id": "evt_000030",
  "task_id": "task_abc123",
  "type": "artifact.created",
  "role": "Writer",
  "status": "created",
  "payload": {
    "artifact_id": "artifact_task_abc123_001",
    "name": "PRD.md",
    "version": 1
  },
  "created_at": "2026-05-30T06:05:00+00:00"
}
```
