# EvoLoop

EvoLoop 是一个围绕任务、会话和文档共创的 agent 工作台。当前仓库包含一套可运行的前后端实现：前端负责任务大厅、会话区、文档编辑区和辅助页面，后端负责任务创建、工作流执行、结构化事件流、知识检索、安全工具调用和 Markdown 产物管理。

当前内置两类任务：

1. `manual`：操作手册编写
2. `prd`：PRD 编写

它们共用同一套任务引擎：`TaskService + WorkflowEngine + ToolService`。

## 当前能力

- 创建和查看 `manual`、`prd` 任务
- 通过 `POST /api/tasks/{task_id}/run` 显式启动或继续任务
- 通过 SSE 订阅结构化任务事件和会话消息
- 在工作台查看和编辑 Markdown 文档，并自动备份旧版本
- 在会话区和文档区对任意选中文本添加引用胶囊
- 查看最近任务、知识卡片、规则卡片和回收站数据
- 在知识检索不可用时返回安全的降级结果，不暴露本地路径和原始私有材料

## 仓库结构

```text
app/
  api/                 # FastAPI 路由与请求/响应 schema
  core/                # Task / Context / Event / Tool / Artifact 核心模型
  services/            # TaskService、ToolService、FileService、Knowledge/GBrain 适配
  workflows/           # 通用 WorkflowEngine 与 manual/prd 任务定义
  格式.md              # manual 任务使用的格式规范资产

frontend/
  src/api.js           # 前端 API helper
  src/pages/Workspace/ # 当前工作台页面与引用交互逻辑

docs/
  architecture/        # 当前 agent 架构说明
  refactor/            # API 契约与后端实现说明

tests/
  test_backend_phase1.py  # 后端行为测试
```

## 运行方式

后端：

```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

前端默认读取 `http://127.0.0.1:8000`，可通过 `VITE_API_BASE` 覆盖。

## 验证

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
npm --prefix frontend run build
```

如果 macOS 或沙盒阻止写入默认 Python cache，请使用上面的 `-X pycache_prefix=/private/tmp/...`。

## 文档入口

- `agent.md`：PM-Agent 核心架构与功能说明
- `AGENTS.md`：仓库协作规则
- `AGENT_MAP.md`：高频修改路径与代码导航
- `GBRAIN_ARCHITECTURE.md`：当前架构文档索引
- `docs/architecture/00-global-architecture.md`：总体运行链路
- `docs/architecture/05-workflow-tool-architecture.md`：任务引擎和 Tool 边界
- `docs/refactor/api-contract.md`：前后端 API/SSE 契约
- `docs/vision/pm_agent_v2_vision.md`：PM-Agent 产品与架构白皮书
