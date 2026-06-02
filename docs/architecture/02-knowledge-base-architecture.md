# 知识检索架构

当前仓库里的知识能力是一个面向工作流的检索适配层，不是独立的知识平台。后端通过 `app/services/gbrain_service.py` 调用本地 `gbrain` 命令，统一把结果整理成安全摘要返回给任务上下文和前端。

## 当前组成

| 组件 | 文件 | 作用 |
|---|---|---|
| 检索适配器 | `app/services/gbrain_service.py` | 调用 `gbrain query` / `gbrain search`，解析 JSON 或文本结果 |
| Tool 封装 | `app/services/tool_service.py` | 通过 `knowledge.retrieve` 暴露给 WorkflowEngine |
| 任务上下文 | `app/core/context.py` | 把检索结果写入 `knowledge_context` 和 `degradation_state` |
| 健康检查接口 | `GET /api/knowledge/health` | 返回知识检索是否可用、结果条数和错误信息 |
| 知识卡片接口 | `GET /api/knowledge` | 返回前端展示用的知识卡片摘要 |

## 当前检索流程

```text
WorkflowEngine 执行 retrieve_knowledge
  -> ToolService.invoke(knowledge.retrieve)
  -> GBrainKnowledge.retrieve(query, scope)
  -> 解析结果并裁剪字段
  -> 写入 TaskContext.knowledge_context
  -> 写入 degradation_state.knowledge
```

## 返回数据特点

当前知识结果只保留安全字段：

- `title`
- `summary`
- `score`（如果上游返回）
- `degraded`
- `error`

不会返回：

- 完整本地路径
- 原始文件内容
- 未授权私有材料原文
- 命令调用细节中的敏感信息

## 降级策略

如果本地 `gbrain` 不可用、超时或结果无法解析，后端返回降级对象：

```json
{
  "query": "...",
  "scope": "default",
  "degraded": true,
  "items": [],
  "error": "gbrain binary not found"
}
```

前端据此显示知识提示和错误状态，但任务仍可继续运行。

## 当前接口边界

- `GET /api/knowledge/health`：返回检索健康状态
- `GET /api/knowledge`：返回前端知识卡片
- `POST /api/knowledge`：当前只创建候选知识卡片数据，不直接写入可信知识存储

这意味着当前实现已经支持“检索”和“展示”，但没有在运行期自动把文档修改沉淀为可信知识。
