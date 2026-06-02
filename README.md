# PM-Agent Platform Backend

这是后端重构 worktree。目标是把项目重构为以 PM-Agent 为核心的双产品线平台，首批支持：

1. `manual`：操作手册编写
2. `prd`：PRD 编写

当前分支只保留新后端骨架；旧 `app/server.py`、`app/main.py`、`app/chat.py`、旧 `app/workflow/*`、旧 `app/agents/*` 和旧静态页面已从本 worktree 删除。

## 目录

```text
app/
  api/                 # FastAPI/API schema 草案
  core/                # TaskDefinition、TaskContext、Event、Artifact、Tool 模型
  services/            # TaskService、ToolService、Event/File/Knowledge 服务与 fakes
  workflows/           # 通用 WorkflowEngine 与 manual/prd TaskDefinition
  格式.md              # manual 格式规范资产，后续迁移到受控资产层

docs/
  architecture/        # 目标架构文档
  refactor/            # 重构计划和 API/SSE 契约

tests/                 # Phase 1 后端单元测试
```

## 核心原则

- `manual` 和 `prd` 都是 `TaskDefinition`，不复制独立 Orchestrator。
- `WorkflowEngine` 只解释 `WorkflowSpec` 和 `StepResult`。
- Agent 不直接读写文件、不直接访问网络、不调用任意 shell。
- 外部能力必须通过 `ToolService`，并受 `ToolPolicy` 白名单约束。
- 前端只消费结构化 API/SSE 事件，不解析后端日志文本。
- Diff 只能生成候选法则，不直接写入 approved 可信法则区。

## API/SSE 契约

后端主维护：

```text
docs/refactor/api-contract.md
```

Antigravity 前端应优先对接：

- `POST /api/tasks`
- `POST /api/tasks/{task_id}/run`
- `GET /api/tasks/{task_id}/events`
- `POST /api/tasks/{task_id}/decisions`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`
- `PUT /api/artifacts/{artifact_id}`
- `POST /api/materials`

## 本地验证

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```

如果 macOS/沙盒阻止写入默认 Python cache，请使用上面的 `-X pycache_prefix=/private/tmp/...`。

## 当前阶段

Phase 1 已完成新后端内核骨架：

- 核心领域模型
- 通用 WorkflowEngine
- ToolService 权限和事件审计
- `manual` / `prd` TaskDefinition
- FakeLLM / FakeKnowledge / FakeStorage
- API skeleton
- 单元测试覆盖状态流转、仲裁暂停恢复、checkpoint 恢复、ToolPolicy、artifact 幂等和 prd 最小工作流

后续阶段再接真实 LLM、真实存储、GBrain、本地材料解析和完整 manual/prd 业务生成策略。
