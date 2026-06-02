# EvoLoop 架构文档索引

文件名沿用历史命名；本文内容只描述当前 EvoLoop agent 的实际架构。

## 文档目录

| 文档 | 说明 |
|---|---|
| [全局架构](docs/architecture/00-global-architecture.md) | 当前产品分层、主流程和运行边界 |
| [前端架构](docs/architecture/01-frontend-architecture.md) | 工作台页面、会话区、文档区和引用交互 |
| [知识检索架构](docs/architecture/02-knowledge-base-architecture.md) | `gbrain` 检索适配、知识卡片接口和降级策略 |
| [Agent 协作架构](docs/architecture/03-triangle-agent-architecture.md) | PM / Tech / QA / Reviewer / Writer 的当前协作方式 |
| [文档与规则流](docs/architecture/04-diff-workflow-architecture.md) | 文档保存、artifact 备份、规则卡片接口 |
| [工作流与 Tool 架构](docs/architecture/05-workflow-tool-architecture.md) | WorkflowEngine、ToolService、checkpoint 和事件流 |
| [后端实现说明](docs/refactor/backend-refactor-plan.md) | 当前后端模块、存储布局和 API 组成 |
| [API/SSE 契约](docs/refactor/api-contract.md) | 前后端协作协议 |
| [产品与架构白皮书](docs/vision/pm_agent_v2_vision.md) | 产品定位、商业化设计与核心架构逻辑 |
## 当前整体关系

```text
任务大厅 / 工作台
  -> FastAPI API
  -> TaskService 创建和调度任务
  -> WorkflowEngine 执行任务步骤
  -> ToolService 调用知识检索、产物写入等受控能力
  -> EventBus + SSE 把状态回放给前端
  -> Artifact 存储当前文档和备份版本
```

## 阅读建议

- 想看产品整体：先读 `docs/architecture/00-global-architecture.md`
- 想改工作台交互：先读 `docs/architecture/01-frontend-architecture.md`
- 想改任务引擎或工具：先读 `docs/architecture/05-workflow-tool-architecture.md`
- 想对接接口：直接读 `docs/refactor/api-contract.md`
