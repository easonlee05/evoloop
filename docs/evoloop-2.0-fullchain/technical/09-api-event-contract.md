# 09 API 与事件契约

本文件是 Evoloop 2.0 的平台级 API/SSE 草案。当前实现方向已迁移到 3.0 主线，相关 API 与技术路线应优先参考 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。

## 1. API 分组

### Workspace

```text
POST /api/workspaces
GET  /api/workspaces/{workspace_id}
PUT  /api/workspaces/{workspace_id}/domain-pack
GET  /api/workspaces/{workspace_id}/packs
```

### Task / DAG

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
GET  /api/tasks/{task_id}/dag-runs
GET  /api/tasks/{task_id}/events
```

### Artifact / Final Save

```text
GET  /api/tasks/{task_id}/document
PUT  /api/tasks/{task_id}/document
POST /api/tasks/{task_id}/save-final
GET  /api/tasks/{task_id}/artifacts
GET  /api/artifacts/{artifact_id}
```

### Evidence / Diff / Rule

```text
GET  /api/tasks/{task_id}/evidence
GET  /api/diff/tasks/{task_id}/candidates
POST /api/diff/tasks/{task_id}/retry
GET  /api/rules/candidates?status=pending|approved|rejected
POST /api/rules/candidates/{rule_id}/review
GET  /api/rules/approved
POST /api/rules/{rule_id}/archive
```

### Knowledge / Material

```text
POST /api/materials
GET  /api/materials/{material_id}
POST /api/materials/{material_id}/parse
GET  /api/knowledge/health
GET  /api/knowledge
POST /api/knowledge/candidates
```

## 2. 关键请求示例

### 保存终稿

```json
{
  "artifact_id": "artifact_task_001_001",
  "content": "# Final PRD\n...",
  "finalize_reason": "用户确认交付"
}
```

响应：

```json
{
  "task_id": "task_001",
  "artifact_id": "artifact_task_001_001",
  "version": 3,
  "status": "final_saved",
  "evidence_id": "evidence_abc123",
  "diff_triggered": true
}
```

### 审核候选法则

```json
{
  "action": "modify_and_approve",
  "modified_title": "对外 API 必须配置限流",
  "modified_content": "新增对外接口时，必须声明限流、熔断和告警策略。",
  "scope": "domain",
  "protection_level": "CRITICAL",
  "review_note": "这是云原生领域强约束"
}
```

## 3. SSE 事件分层

| 前缀 | 示例 | 含义 |
|---|---|---|
| `task.*` | `task.created`, `task.completed` | 任务生命周期。 |
| `dag.*` | `dag.plan.proposed`, `dag.node.started` | DAG 计划和节点状态。 |
| `agent.*` | `agent.message.completed` | Agent 输出。 |
| `tool.*` | `tool.call.started`, `tool.call.denied` | Tool 审计。 |
| `blackboard.*` | `blackboard.merge.conflict` | 状态合并。 |
| `arbitration.*` | `arbitration.requested` | 用户裁决。 |
| `artifact.*` | `artifact.created`, `artifact.final_saved` | 产物。 |
| `evidence.*` | `evidence.frozen` | 证据冻结。 |
| `diff.*` | `diff.candidates_ready` | Diff 学习。 |
| `rule.*` | `rule.approved`, `rule.stored` | 法则审核入库。 |
| `knowledge.*` | `knowledge.degraded` | 知识检索健康。 |

## 4. 事件 payload 安全要求

事件不得包含：

- API key、token、authorization header。
- 服务器绝对路径。
- 未授权材料全文。
- 原始 prompt 全文。
- GBrain 私有页面全文，除非用户通过授权 API 请求。

事件应该包含：

- ID 引用。
- 安全摘要。
- 状态。
- 用户可理解的下一步提示。

## 5. 回放原则

SSE 首先回放 `events.jsonl` 中已持久化事件，再接入实时 Event Bus。前端刷新页面不应丢失任务状态。
