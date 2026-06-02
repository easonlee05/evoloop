# Agent Map

这是当前 EvoLoop agent 仓库的导航图。`manual` 和 `prd` 都通过同一个任务引擎执行，不需要分别查找独立 orchestrator。

## 首读顺序

1. `AGENTS.md`
2. `README.md`
3. `GBRAIN_ARCHITECTURE.md`
4. `docs/refactor/api-contract.md`
5. 用 `rg` 定位相关模型、页面或接口

默认不要读取 `.env`、`workspace/outputs/`、`workspace/inputs/temp/` 和完整材料库。

## 后端核心入口

| 文件 | 作用 |
|---|---|
| `app/core/task.py` | `TaskDefinition`、`WorkflowSpec`、`WorkflowStep`、`StepResult`、任务状态。 |
| `app/core/context.py` | `TaskContext`、`UserDecision`、共享上下文。 |
| `app/core/events.py` | `Event` 与 `EventBus`，供 API 和 SSE 回放。 |
| `app/core/tools.py` | `ToolSpec`、`ToolCall`、`ToolResult`、`ToolPolicy`。 |
| `app/workflows/definitions.py` | `manual` / `prd` 任务定义注册表。 |
| `app/workflows/manual.py` | 操作手册任务定义。 |
| `app/workflows/prd.py` | PRD 任务定义。 |
| `app/workflows/engine.py` | 通用任务引擎，负责步骤执行、并行组、仲裁暂停与恢复。 |
| `app/services/task_service.py` | 创建、运行、恢复、取消、删除任务。 |
| `app/services/tool_service.py` | Tool 注册、白名单校验、审计事件。 |
| `app/services/file_service.py` | 文档读写和备份封装。 |
| `app/services/gbrain_service.py` | 本地 `gbrain` 检索适配与安全降级。 |
| `app/api/server.py` | FastAPI API、SSE、任务列表、文档和辅助页面接口。 |
| `tests/test_backend_phase1.py` | 当前后端行为测试。 |

## 前端核心入口

| 文件 | 作用 |
|---|---|
| `frontend/src/api.js` | 前端统一请求封装。 |
| `frontend/src/pages/Workspace/index.jsx` | 工作台主页面：会话区、文档区、引用交互、任务动作。 |
| `frontend/src/pages/Workspace/workspace.css` | 当前工作台样式。 |
| `frontend/src/pages/Workspace/quoteSelection.js` | 引用胶囊、悬浮文案和字数限制逻辑。 |
| `frontend/src/pages/Workspace/workspaceSession.js` | 控制是否自动打开文档、是否自动执行任务。 |
| `frontend/src/pages/Workspace/workspaceActions.js` | 文档按钮文案和继续运行提示逻辑。 |

## 关键链路

```text
POST /api/tasks
  -> TaskService.create_task
  -> TaskDefinition 注册表选择 manual/prd
  -> 生成 TaskContext 并写入 task.json/context.json

POST /api/tasks/{task_id}/run
  -> WorkflowEngine.run
  -> 按 WorkflowSpec 执行 context / agent / gate / arbitration / artifact / checkpoint
  -> ToolService 统一处理知识检索、产物写入等能力
  -> EventBus + events.jsonl 提供回放与 SSE

GET /api/tasks/{task_id}/document
PUT /api/tasks/{task_id}/document
  -> 读取或更新当前 Markdown 文档
  -> 更新前先备份旧 artifact
```

## 常见修改路径

- 任务类型或工作流步骤：`app/workflows/`
- 任务状态、共享上下文、事件模型：`app/core/`
- API 字段和 SSE 事件：`app/api/server.py`、`docs/refactor/api-contract.md`
- 文档读写、备份、知识检索：`app/services/`
- 工作台交互：`frontend/src/pages/Workspace/`
- 前后端请求封装：`frontend/src/api.js`

## 约束摘要

- Agent 不直接读写文件；文档写入必须走 `artifact.write` 或文档保存接口。
- Tool 权限不足返回 `denied`，并输出 `tool.call.denied`。
- 前端只消费结构化 API/SSE，不解析后端日志文本。
- 文档、知识和规则接口都不能暴露完整本地路径或未授权原文。

## 验证

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
npm --prefix frontend run build
```
