# API/SSE Contract for PM-Agent Platform

本文档是后端主维护的前后端契约。Antigravity 前端只消费这里定义的 HTTP API、Artifact 资源和结构化 SSE 事件，不解析后端日志文本。

## 1. Contract Principles

- 所有任务类型都通过 `TaskDefinition` 创建，首期支持 `manual` 和 `prd`。
- 前端通过 SSE 消费结构化事件，不读取 console 日志协议。
- 事件 payload 不包含凭证、完整本地路径、未授权材料原文或 `.env` 内容。
- Tool 权限不足返回 `tool.call.denied`，不伪装成普通失败。
- 用户裁决是正常流程：`arbitration.requested` 后任务暂停，`arbitration.applied` 后从 `resume_step_id` 恢复。

## 2. Common Objects

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

## 3. Endpoints

### POST /api/tasks

Create a task shell and persist `task.json`, `context.json`, and a `task.created` event.

EvoLoop frontend compatibility: the landing page may send only `{ "prompt": "..." }`. Backend infers `type` (`prd` by default, `manual` when the prompt mentions 操作手册/manual), fills `username` as `frontend`, and returns both snake_case and camelCase ids.

Request fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `type` | string | yes | `manual` or `prd` |
| `username` | string | yes | Workspace/user isolation key |
| `title` | string | no | Display title |
| `goal` | string | no | Generic task goal |
| `material_ids` | string[] | no | Uploaded material ids |

Response:

```json
{
  "task_id": "task_abc123",
  "taskId": "task_abc123",
  "id": "task_abc123",
  "status": "created"
}
```

### GET /api/tasks

List task rows for the EvoLoop task hall. `status` is frontend-facing and maps backend states to `running | review | pending | done`.

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

### POST /api/tasks/{task_id}/run

Start or resume task execution from the latest checkpoint. If a task reaches arbitration it returns `waiting_for_user`.

Response:

```json
{
  "task_id": "task_abc123",
  "status": "waiting_for_user",
  "waiting_step_id": "arbitration_business_tradeoff"
}
```

### POST /api/tasks/{task_id}/interrupt

Frontend pause/interrupt endpoint. Phase 1 maps it to safe task cancellation and emits `task.cancelled`; it must not mark unfinished artifacts as completed.

```json
{
  "task_id": "task_abc123",
  "taskId": "task_abc123",
  "status": "cancelled"
}
```

### GET /api/tasks/{task_id}/events

SSE replay stream. Phase 1 replays stored `events.jsonl`; later phases can keep the stream open for live events.
Each SSE `data` object may include `frontend_message`, a presentation helper shaped like Claude's workspace message model. Frontend may render it directly but must still treat the canonical event fields as source of truth.

SSE frame:

```text
id: evt_000012
event: workflow.step.completed
data: {"id":"evt_000012","task_id":"task_abc123","type":"workflow.step.completed","payload":{"step_id":"pm_draft"}}
```

### GET /api/tasks/{task_id}/document

Read the latest task Markdown document for the workspace editor. If the task has no artifact yet, backend may run the Phase 1 workflow once to produce the first artifact.

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

### PUT /api/tasks/{task_id}/document

Save frontend editor changes. Backend backs up the previous artifact and increments the existing artifact version when content changes.

```json
{
  "content": "# Updated PRD\n"
}
```

Response:

```json
{
  "artifact_id": "artifact_task_abc123_001",
  "artifactId": "artifact_task_abc123_001",
  "version": 2,
  "content": "# Updated PRD\n"
}
```

### POST /api/tasks/{task_id}/decisions

Apply a user arbitration decision, append it to `TaskContext.user_decisions`, emit `arbitration.applied`, and resume from the backend-declared `resume_step_id`.

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

`quoted_selections` is optional. Frontend may send it when the user quotes text from the conversation area or editor before submitting a decision.

Response:

```json
{
  "task_id": "task_abc123",
  "status": "completed"
}
```

### GET /api/tasks/{task_id}/artifacts

List artifacts for a task.

Response:

```json
{
  "artifacts": [
    {
      "artifact_id": "artifact_task_abc123_001",
      "task_id": "task_abc123",
      "name": "PRD.md",
      "version": 1,
      "content_type": "text/markdown",
      "created_by": "Writer",
      "summary": "Generated PRD.md"
    }
  ]
}
```

### GET /api/artifacts/{artifact_id}

Read an artifact. The response may include Markdown content but must not expose server-local absolute paths.

```json
{
  "artifact_id": "artifact_task_abc123_001",
  "task_id": "task_abc123",
  "name": "PRD.md",
  "version": 1,
  "content_type": "text/markdown",
  "created_by": "Writer",
  "summary": "Generated PRD.md",
  "content": "# 工单升级 PRD\n"
}
```

### PUT /api/artifacts/{artifact_id}

Update an artifact from the frontend editor. Backend must create a backup before writing a new version. Phase 1 keeps idempotent same-name writes; later phases should increment version when content changes.

Request:

```json
{
  "content": "# Updated PRD\n"
}
```

### POST /api/materials

Upload a material into the material library. Uploads do not directly write trusted knowledge.

Response:

```json
{
  "material_id": "material_abc123",
  "status": "uploaded",
  "summary": "source.pdf uploaded; full local path is not exposed."
}
```

### GET /api/knowledge

List frontend knowledge cards. Phase 1 returns safe summaries only, never full local paths or raw private materials.

### POST /api/knowledge

Create a candidate knowledge item. Upload parsing into trusted knowledge remains a later Tool-mediated flow.

### GET /api/rules?status=pending|approved|rejected

List Diff Agent candidate or reviewed rules for the rule audit page. Candidate rules are not written to approved trusted memory until explicitly approved.

### POST /api/rules/{rule_id}/approve

Approve a candidate rule, optionally with edited content.

### POST /api/rules/{rule_id}/reject

Reject a candidate rule.

### GET /api/recycle

List soft-deleted demo items for the recycle bin.

### POST /api/recycle/{item_id}/restore

Restore a soft-deleted item.

### DELETE /api/recycle/{item_id}

Permanently delete a soft-deleted item. Phase 1 endpoint is a demo surface and does not delete user materials or outputs.

### GET /api/conversations/recent

Return recent task links for the sidebar.

## 4. Task Request Examples

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

## 5. Event Examples

### arbitration.requested

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

### arbitration.applied

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

### workflow.step.started

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

### workflow.step.completed

```json
{
  "id": "evt_000005",
  "task_id": "task_abc123",
  "type": "workflow.step.completed",
  "role": "PM",
  "status": "succeeded",
  "payload": {
    "step_id": "pm_draft",
    "summary": "PM completed"
  },
  "created_at": "2026-05-30T06:00:01+00:00"
}
```

### workflow.step.failed

```json
{
  "id": "evt_000009",
  "task_id": "task_abc123",
  "type": "workflow.step.failed",
  "role": "Reviewer",
  "status": "failed",
  "payload": {
    "step_id": "reviewer_gate",
    "error": {
      "code": "gate.failed",
      "message": "目标一致性未通过"
    }
  },
  "created_at": "2026-05-30T06:00:02+00:00"
}
```

### tool.call.started

```json
{
  "id": "evt_000002",
  "task_id": "task_abc123",
  "type": "tool.call.started",
  "role": "SYSTEM",
  "status": "started",
  "payload": {
    "tool_name": "knowledge.retrieve",
    "step_id": "retrieve_knowledge",
    "role": "SYSTEM",
    "summary": "started"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### tool.call.completed

```json
{
  "id": "evt_000003",
  "task_id": "task_abc123",
  "type": "tool.call.completed",
  "role": "SYSTEM",
  "status": "succeeded",
  "payload": {
    "tool_name": "knowledge.retrieve",
    "step_id": "retrieve_knowledge",
    "role": "SYSTEM",
    "summary": "knowledge retrieved"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### tool.call.failed

```json
{
  "id": "evt_000030",
  "task_id": "task_abc123",
  "type": "tool.call.failed",
  "role": "SYSTEM",
  "status": "failed",
  "payload": {
    "tool_name": "material.parse",
    "step_id": "ingest_materials",
    "role": "SYSTEM",
    "summary": "unsupported file type"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### tool.call.denied

```json
{
  "id": "evt_000031",
  "task_id": "task_abc123",
  "type": "tool.call.denied",
  "role": "PM",
  "status": "denied",
  "payload": {
    "tool_name": "artifact.write",
    "step_id": "pm_draft",
    "role": "PM",
    "summary": "PM cannot call artifact.write in pm_draft"
  },
  "created_at": "2026-05-30T06:00:00+00:00"
}
```

### artifact.created

```json
{
  "id": "evt_000040",
  "task_id": "task_abc123",
  "type": "artifact.created",
  "role": "Writer",
  "status": "created",
  "payload": {
    "artifact_id": "artifact_task_abc123_001",
    "name": "PRD.md",
    "version": 1
  },
  "created_at": "2026-05-30T06:00:03+00:00"
}
```

### task.failed

```json
{
  "id": "evt_000050",
  "task_id": "task_abc123",
  "type": "task.failed",
  "status": "failed",
  "payload": {
    "step_id": "reviewer_gate"
  },
  "created_at": "2026-05-30T06:00:04+00:00"
}
```

### task.cancelled

```json
{
  "id": "evt_000051",
  "task_id": "task_abc123",
  "type": "task.cancelled",
  "status": "cancelled",
  "payload": {
    "reason": "user_cancelled"
  },
  "created_at": "2026-05-30T06:00:04+00:00"
}
```

## 6. Frontend Integration Notes

- Create task with `POST /api/tasks`, then call `POST /api/tasks/{task_id}/run`.
- Subscribe to `GET /api/tasks/{task_id}/events`; render UI from event type, role, status and payload.
- When `arbitration.requested` arrives, show `dispute_package.options` and post the user's decision to `/decisions`.
- Use `/artifacts` and `/api/artifacts/{artifact_id}` for the file tree and Markdown editor.
- Do not read backend filesystem paths, Python logs, or old `[__CHAT_MSG_START__|PM]` markers.
