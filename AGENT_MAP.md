# Agent Map

这是新后端重构 worktree 的导航图。不要再按旧 `app/server.py`、旧 `app/workflow/orchestrator.py` 或旧 `app/agents/*` 查找主架构；这些旧实现已删除。

## 一句话

本仓库正在重构为 PM-Agent 双产品线平台后端。`manual` 和 `prd` 都通过同一个 `TaskService + WorkflowEngine + ToolService` 执行。

## 首读规则

1. 先读 `AGENTS.md`。
2. 再读 `GBRAIN_ARCHITECTURE.md` 和 `docs/architecture/05-workflow-tool-architecture.md`。
3. API 对接先读 `docs/refactor/api-contract.md`。
4. 用 `rg` 定位相关模型或步骤，不要默认读取 `.env`、用户材料、输出产物或完整样例库。

## 核心入口

| 文件 | 作用 |
|---|---|
| `app/core/task.py` | `TaskDefinition`、`WorkflowSpec`、`StepResult`、任务/步骤状态。 |
| `app/core/context.py` | `TaskContext`、用户裁决、任务上下文。 |
| `app/core/events.py` | 结构化事件模型，供 SSE/API 回放。 |
| `app/core/tools.py` | `ToolSpec`、`ToolCall`、`ToolResult`、`ToolPolicy`。 |
| `app/workflows/engine.py` | 通用 WorkflowEngine，不硬编码 manual/prd 业务路径。 |
| `app/workflows/definitions.py` | `manual` 和 `prd` 任务定义注册表。 |
| `app/workflows/manual.py` | manual TaskDefinition skeleton。 |
| `app/workflows/prd.py` | prd TaskDefinition 最小可运行工作流。 |
| `app/services/task_service.py` | 创建、运行、恢复、取消任务。 |
| `app/services/tool_service.py` | Tool 注册、权限校验、调用审计和事件输出。 |
| `app/services/fakes.py` | FakeLLM / FakeKnowledge / FakeStorage，本地测试用。 |
| `app/api/server.py` | Phase 1 API skeleton。 |
| `frontend/src/api.js` | EvoLoop 前端 API helper，仅负责数据请求，不承载样式。 |
| `docs/refactor/api-contract.md` | 前后端 API/SSE 契约，后端主维护。 |
| `tests/test_backend_phase1.py` | Phase 1 行为测试。 |

## 新工作流

```text
POST /api/tasks
  -> TaskService.create_task
  -> TaskDefinition 注册表选择 manual/prd
  -> TaskContext 初始化

POST /api/tasks/{task_id}/run
  -> WorkflowEngine.run
  -> 解释 WorkflowSpec steps
  -> 通过 ToolService 调用 material/knowledge/artifact/format/diff/event 工具
  -> 每步写 checkpoint
  -> 输出结构化 Event
  -> 需要仲裁时 waiting_for_user
  -> 收到 decisions 后从 resume_step_id 恢复
```

## 前端联调

- Claude 前端位于 `frontend/`，仓库 `.gitignore` 已改为只忽略根目录 `/workspace/`，避免误伤工作台页面 `frontend/src/pages/Workspace/`。
- 不要轻易修改 `frontend/**/*.css` 和设计 token；对接优先改 `frontend/src/api.js` 与页面数据请求。
- Vite 默认端口 4000，后端 FastAPI 默认端口 8000；可通过 `VITE_API_BASE` 指向其他后端地址。

## Tool 边界

首期 Tool：

- `material.read`
- `material.parse`
- `knowledge.retrieve`
- `artifact.write`
- `artifact.read`
- `artifact.backup`
- `format.validate`
- `diff.extract_rules`
- `event.emit`

所有 write/external 类型 Tool 必须发 `tool.call.started` 和 `tool.call.completed/failed/denied`。

## 验证

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```

## 旧代码状态

旧后端入口、旧 orchestrator、旧 agent 实现和旧静态页面已从当前 worktree 删除。`app/格式.md` 暂时保留为 manual 格式规范迁移资产。
