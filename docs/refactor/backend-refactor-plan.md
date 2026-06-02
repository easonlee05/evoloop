# 后端实现说明

本文描述 EvoLoop 后端服务的实际架构与具体实现。

## 当前目标

当前后端服务负责三件事：

1. 创建并运行 `manual`、`prd` 两类任务
2. 通过结构化事件把任务进度同步给前端工作台
3. 管理 Markdown 文档、备份版本、知识检索和规则/回收站等辅助接口

## 当前模块划分

| 模块 | 文件 | 作用 |
|---|---|---|
| 核心模型 | `app/core/` | 定义任务、上下文、事件、artifact、Tool 协议 |
| 工作流 | `app/workflows/` | 定义 `manual` / `prd` 工作流和通用执行引擎 |
| 应用服务 | `app/services/` | 任务调度、工具调用、文档读写、知识检索 |
| API | `app/api/` | 暴露 HTTP 接口和 SSE |
| 测试 | `tests/test_backend_phase1.py` | 覆盖当前主要行为 |

## 当前任务模型

### TaskDefinition

当前所有任务都通过 `TaskDefinition` 描述，不为每个任务类型复制一套独立执行器。

当前注册：

- `manual`
- `prd`

### TaskContext

每个任务都有独立 `TaskContext`，当前用于保存：

- 基础输入和标题
- 用户约束
- 材料摘要
- 知识检索结果
- 回合历史
- 用户裁决
- 门禁结果
- 已写入的 artifact
- 步骤输出与降级状态

### Event

所有任务状态变化都通过 `Event` 记录到 `events.jsonl`，同时可经由 `EventBus` 推送给正在订阅 SSE 的前端。

## 当前工作流

### manual

当前 `manual` 工作流：

```text
ingest_materials
  -> build_context
  -> retrieve_knowledge
  -> pm_outline_and_questions
  -> tech_fact_check / qa_operability_check
  -> reviewer_plan_gate
  -> writer_overview
  -> writer_scene_docs
  -> reviewer_document_gate
  -> write_manual_artifact
  -> final_checkpoint
```

### prd

当前 `prd` 工作流：

```text
build_context
  -> retrieve_knowledge
  -> pm_draft
  -> tech_challenge / qa_challenge
  -> pm_first_draft
  -> tech_review / qa_review
  -> convergence_gate
  -> arbitration_business_tradeoff
  -> pm_after_arbitration
  -> reviewer_gate
  -> writer_final_prd
  -> write_prd_artifact
  -> final_checkpoint
```

## 当前 API 组成

主入口位于 `app/api/server.py`，当前对外提供：

- 任务创建、列表、详情、执行、取消、删除、恢复
- SSE 事件流和前端消息辅助字段
- 文档读取、更新、artifact 列表与详情
- 材料上传
- 知识卡片与知识健康检查
- 规则审核卡片接口
- 回收站接口
- 最近任务接口

完整字段见 `docs/refactor/api-contract.md`。

## 当前存储行为

后端默认使用本地文件存储：

- `task.json` 保存任务元数据
- `context.json` 保存共享上下文
- `checkpoint.json` 保存恢复点
- `events.jsonl` 保存结构化事件
- `artifact_*.json` 保存当前文档
- `backup_*.json` 保存旧版本备份

## 当前知识能力

知识检索通过 `GBrainKnowledge` 适配本地 `gbrain` 命令完成：

- 能解析 JSON 或文本结果
- 统一裁剪成安全摘要
- 在不可用时返回降级对象
- 支持 `/api/knowledge/health` 暴露当前状态

## 当前 Tool 边界

任务运行过程中，外部能力统一从 `ToolService` 进入，当前重点工具包括：

- `knowledge.retrieve`
- `artifact.write`
- `artifact.read`
- `artifact.backup`
- `material.read`
- `material.parse`

Tool 权限不通过时返回 `denied`，并发出对应事件。

## 当前和前端的配合方式

前端只依赖 API 与 SSE：

- 不解析后端日志文本
- 不直连模型
- 不直接写入本地文件
- 打开文档、继续任务、提交裁决都走显式操作

## 当前验证命令

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
npm --prefix frontend run build
```
