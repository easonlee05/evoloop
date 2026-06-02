# 全局架构

EvoLoop 当前是一套围绕任务、会话和 Markdown 文档共创的 agent 工作台。系统由前端工作台、FastAPI API、通用任务引擎、知识检索适配和 artifact 存储组成。

- [前端架构](01-frontend-architecture.md)
- [知识检索架构](02-knowledge-base-architecture.md)
- [Agent 协作架构](03-triangle-agent-architecture.md)
- [文档与规则流](04-diff-workflow-architecture.md)
- [工作流与 Tool 架构](05-workflow-tool-architecture.md)

## 当前分层

| 层 | 主要文件 | 职责 |
|---|---|---|
| 前端工作台 | `frontend/src/pages/Workspace/` | 任务列表、会话区、文档区、引用胶囊、知识提示、任务动作 |
| API 层 | `app/api/server.py` | 暴露任务、SSE、文档、知识、规则、回收站等接口 |
| 应用服务层 | `app/services/task_service.py`、`app/services/tool_service.py` | 创建任务、运行任务、校验工具权限、输出审计事件 |
| 工作流层 | `app/workflows/engine.py`、`app/workflows/manual.py`、`app/workflows/prd.py` | 解释任务定义并推进步骤 |
| 核心模型层 | `app/core/*.py` | 定义任务、上下文、事件、工具、artifact 的统一模型 |
| 存储与知识层 | `app/services/fakes.py`、`app/services/file_service.py`、`app/services/gbrain_service.py` | 保存任务文件、artifact、checkpoint，执行知识检索与降级 |

## 当前主流程

```text
用户创建任务
  -> 后端生成 TaskContext 和 task.json
  -> 用户显式点击继续运行
  -> WorkflowEngine 按任务定义执行步骤
  -> Agent 步骤流式输出消息并写入 round_history
  -> Gate 判断是否通过或需要用户裁决
  -> Writer 生成 Markdown，artifact.write 持久化文档
  -> 前端读取最新文档并允许继续编辑
  -> 用户保存文档时自动备份旧版本
```

## 当前支持的任务

| 任务类型 | 输入重点 | 输出文档 | 特点 |
|---|---|---|---|
| `manual` | `module_name`、材料、补充说明 | `模块概览.md` | 适合操作手册和模块说明 |
| `prd` | `feature`、`business_goal`、约束 | `PRD.md` | 带 PM / Tech / QA / Reviewer / Writer 协作与仲裁能力 |

## 当前存储布局

```text
<storage_root>/
  tasks/
    task_xxx/
      task.json
      context.json
      checkpoint.json
      events.jsonl
  artifacts/
    artifact_task_xxx_001.json
    backup_artifact_task_xxx_001_v1.json
```

默认本地运行时，后端使用临时目录作为存储根目录。

## 当前边界

- 前端不直接调用模型，也不直接写本地文件。
- Agent 不直接读写文件；受控能力统一通过 ToolService。
- 文档保存通过 artifact 接口完成，并在更新前创建备份。
- 知识检索只返回安全摘要，不返回完整本地路径或未授权原文。
- 所有关键状态变化通过结构化事件输出，前端不解析后端日志文本。
