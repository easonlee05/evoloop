# AGENTS.md — PM-Agent 平台工作规则

> 适用工具：Claude Code、Codex、Antigravity 及所有 AI 编程工具。
> 本仓库当前以 `AGENT_MAP.md`、`docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md` 作为导航与实现路线来源。

---

## 工作规则

**不要先通读整个仓库。** 按以下顺序读：

1. 本文件：职责边界、禁止事项、验证方式
2. `AGENT_MAP.md`：仓库导航、文件职责、常见修改路径
3. `docs/evoloop-3.0/architecture/00-global-architecture.md`：3.0 架构真相源
4. `docs/evoloop-3.0/technical/00-evolution-roadmap.md`：1.0 到 3.0 技术演进路线
5. `docs/evoloop-3.0/technical/01-parallel-development-boundaries.md`：并行开发边界规范
6. 用 `rg` 定位相关符号，只展开与任务直接相关的模块

**重要：**
- `docs/evoloop-2.0-fullchain/` 和 `docs/vision/pm_agent_v2_vision.md` 只作为历史参考，不再作为当前目标架构真相源。
- 如果 2.0 文档与 3.0 文档冲突，始终以 3.0 文档为准。

**默认不读：**
- `.env`：可能含凭证
- `workspace/outputs/`：生成产物
- `workspace/inputs/temp/`：截图和临时材料
- `workspace/inputs/knowledge/` 和 `workspace/inputs/samples/`：仅在材料/调试任务时读

**不要修改：**
- 用户材料和输出产物
- 未授权的完整 knowledge/samples
- 前端样式文件，除非用户明确要求或 Antigravity/Claude 给出设计变更

---

## 当前目标架构

本仓库当前目标是 Evoloop 3.0：以“数字产品经理”作为系统核心，而不是以 PRD/操作手册生成作为中心。

3.0 的主方向是：

- 把业务意图编译为 AI 可执行规格、任务包和验收协议
- 让 Codex / Claude Code / Cursor 等 AI worker 成为下游执行者
- 通过 Decision Gate、Artifact Graph、Acceptance Review 和长期产品记忆形成闭环

现有 `manual` 和 `prd` 仍然存在，但在 3.0 中应被视为 legacy playbook 或可选 artifact，而不是系统最终产品定位。

旧 `app/workflow/orchestrator.py`、`app/workflow/prd_orchestrator.py`、`app/server.py`、`app/chat.py`、`app/main.py` 不再是主架构入口。

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
| Contract | `docs/evoloop-3.0/technical/00-evolution-roadmap.md` | 当前实现路线与重构阶段真相源 |

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
- 后端主维护 3.0 文档和实现路线；前端提出变更后，由后端统一更新对应文档与实现边界。
- `frontend/src/pages/Workspace/` 是有效工作台页面；根目录 `.gitignore` 只忽略 `/workspace/`，避免误伤该页面。

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
