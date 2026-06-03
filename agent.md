# Agent Handoff

本 worktree 是后端重构分支，路径：

```text
/Users/apple/.codex/worktrees/5062/manual-agent
```

当前状态：后端 Phase 1 骨架已完成，旧后端实现已从本 worktree 删除。不要再查找或依赖旧入口 `app/server.py`、`app/main.py`、`app/chat.py`、旧 `app/workflow/*`、旧 `app/agents/*`、旧 `app/static/*`。

## 后端新架构入口

优先阅读：

```text
AGENT_MAP.md
docs/evoloop-3.0/architecture/00-global-architecture.md
docs/evoloop-3.0/technical/00-evolution-roadmap.md
docs/evoloop-3.0/technical/01-parallel-development-boundaries.md
app/core/task.py
app/workflows/engine.py
app/workflows/definitions.py
app/services/task_service.py
app/services/tool_service.py
```

当前保留的新后端目录：

```text
app/api/          # API skeleton 和请求/响应 schema
app/core/         # TaskDefinition、TaskContext、Event、Artifact、Tool 模型
app/services/     # TaskService、ToolService、Event/File/Knowledge 服务和 fakes
app/workflows/    # 通用 WorkflowEngine、manual/prd TaskDefinition
app/格式.md       # manual 格式规范迁移资产
```

## 前端/Antigravity 对接

前端和实现方应优先参考 3.0 主线文档：

```text
docs/evoloop-3.0/architecture/00-global-architecture.md
docs/evoloop-3.0/technical/00-evolution-roadmap.md
```

首期接口：

- `POST /api/tasks`
- `POST /api/tasks/{task_id}/run`
- `GET /api/tasks/{task_id}/events`
- `POST /api/tasks/{task_id}/decisions`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`
- `PUT /api/artifacts/{artifact_id}`
- `POST /api/materials`

前端不要解析后端日志文本，不要依赖旧 `[__CHAT_MSG_START__|PM]` 标记。UI 状态应完全由结构化事件驱动。

## 后端边界

- `manual` 和 `prd` 都是 `TaskDefinition`，不能复制独立 Orchestrator。
- `WorkflowEngine` 只解释 `WorkflowSpec` 和 `StepResult`，不写死业务路径。
- Agent 不直接读写文件、不直接访问网络、不调用任意 shell。
- 外部能力必须通过 `ToolService`，并受 `ToolPolicy` 白名单约束。
- 所有 write/external Tool 必须产生 `tool.call.started` 和 `tool.call.completed/failed/denied` 事件。
- `needs_arbitration` 是正常暂停状态，用户提交裁决后从 `resume_step_id` 恢复。

## 验证命令

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```

## 还没完成的后续工作

- 接真实 LLMPort 和真实 Agent prompt。
- 接真实存储、材料上传、材料解析和 GBrain/本地知识检索。
- 完成 manual/prd 的完整业务生成策略。
- API skeleton 接入生产级鉴权、持久化和 live SSE。
- Diff 候选法则审核入库流程。
