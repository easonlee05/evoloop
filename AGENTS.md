# AGENTS.md — PM-Agent 平台工作规则

> 适用工具：Claude Code、Codex、Antigravity 及所有 AI 编程工具。
> 本仓库以 `AGENT_MAP.md` 和 `docs/refactor/api-contract.md` 作为导航与前后端契约来源。

---

## 工作规则

**不要先通读整个仓库。** 按以下顺序读：

1. 本文件：职责边界、禁止事项、验证方式
2. `AGENT_MAP.md`：仓库导航、文件职责、常见修改路径
3. `docs/refactor/api-contract.md`：前后端 API/SSE 契约
4. 用 `rg` 定位相关符号，只展开与任务直接相关的模块

**默认不读：**
- `.env`：可能含凭证

**不要修改：**
- 用户材料和输出产物
- 未授权的完整 knowledge/samples
- 前端样式文件，除非用户明确要求或 Antigravity/Claude 给出设计变更

---

## 平台架构

本仓库是以 PM-Agent 为核心的双产品线平台：

- `manual`：操作手册编写
- `prd`：PRD 编写

`manual` 和 `prd` 均基于同一个通用任务引擎下的 `TaskDefinition` 进行调度。

核心后端分层：

| 层 | 文件 | 职责 |
|---|---|---|
| Core | `app/core/task.py` | `TaskDefinition`、`WorkflowSpec`、`StepResult`、状态模型 |
| Core | `app/core/context.py` | `TaskContext`、用户裁决、上下文 |
| Core | `app/core/events.py` | 结构化事件模型，供 API/SSE 回放 |
| Core | `app/core/tools.py` | `ToolSpec`、`ToolCall`、`ToolResult`、`ToolPolicy` |
| Workflow | `app/workflows/engine.py` | 通用 WorkflowEngine，只解释 spec/result |
| Workflow | `app/workflows/manual.py` | manual TaskDefinition |
| Workflow | `app/workflows/prd.py` | prd TaskDefinition |
| Service | `app/services/task_service.py` | 创建、运行、恢复、取消任务 |
| Service | `app/services/tool_service.py` | Tool 白名单、权限、事件审计 |
| API | `app/api/server.py` | FastAPI API/SSE surface |
| Frontend | `frontend/src/api.js` | EvoLoop 前端 API helper |
| Contract | `docs/refactor/api-contract.md` | 后端主维护的前后端契约 |

---

## Workflow / Tool 约束

- Workflow 是任务执行控制面，负责步骤编排、状态流转、暂停恢复、重试取消、checkpoint、事件输出和产物交接。
- Tool 是受控能力调用层，负责材料读取、材料解析、知识检索、产物写入、备份、格式校验、Diff 提炼和事件输出。
- Agent 不允许直接读写文件、调用任意 shell、访问网络或绕过 `TaskContext`。
- Agent 只能请求 `TaskDefinition.tool_policy` 白名单中的 Tool。
- Writer 写产物必须通过 `artifact.write` Tool。
- Diff 只能生成候选法则，不能直接写入 approved 可信法则区。
- 所有 write/external 类型 Tool 必须产生 `tool.call.started` 与 `tool.call.completed/failed/denied` 事件。
- 权限不足必须返回 denied，不要伪装成 failed。
- 事件 payload 不得泄露凭证、完整本地路径或未授权材料原文。

---

## 前端协作规则

- Antigravity/Claude 负责 `frontend/` UI 与样式；Codex 后端只做必要 API 接入。
- 不要轻易改 `frontend/**/*.css` 或设计 token。
- 前端通过稳定 API/SSE 协议协作，不解析后端日志文本。
- 后端主维护 `docs/refactor/api-contract.md`；前端提出变更后，由后端统一更新契约。
- `frontend/src/pages/Workspace/` 是有效工作台页面。

---

## 快速验证

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
npm --prefix frontend run build
```

本地联调：

```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
npm --prefix frontend run dev
```

前端默认读取 `http://127.0.0.1:8000`，可通过 `VITE_API_BASE` 覆盖。
