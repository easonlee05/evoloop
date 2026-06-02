# GBrain 架构文档索引

本文档是目标架构索引。后续维护以这里列出的架构边界为准。

## 文档目录

| 文档 | 说明 |
|---|---|
| [全局架构](docs/architecture/00-global-architecture.md) | 总体分层、主流程、边界原则和路线图 |
| [前台架构](docs/architecture/01-frontend-architecture.md) | 共创客户端、实时直播、用户打断、死锁仲裁和法则审核 |
| [知识库架构](docs/architecture/02-knowledge-base-architecture.md) | GBrain 的知识导入、索引、检索、可信法则存储和降级快照 |
| [中台铁三角架构](docs/architecture/03-triangle-agent-architecture.md) | PM、Tech、QA、Reviewer 的任务沙盒、攻防闭环和门禁机制 |
| [Diff 流程架构](docs/architecture/04-diff-workflow-architecture.md) | 终稿证据冻结、候选法则提炼、人工审核和可信入库 |
| [工作流与 Tool 架构](docs/architecture/05-workflow-tool-architecture.md) | 可暂停编排、步骤协议、受控工具调用、权限审计和事件透明 |

## 总体关系

```text
前台共创客户端
  -> 中台铁三角任务沙盒
  -> GBrain 知识检索
  -> Workflow Engine 按步骤推进并通过 Tool Service 调用受控能力
  -> 终稿保存
  -> Diff 流程提炼候选法则
  -> 前台人工审核
  -> GBrain 可信法则入库
```

![GBrain 全栈架构拓扑](assets/gbrain-fullstack-topology.png)

## 维护原则

- 全局链路、分层和路线图写入全局架构。
- 页面交互、打断、仲裁和审核入口写入前台架构。
- 知识导入、索引、检索、可信法则存储和快照写入知识库架构。
- PM、Tech、QA、Reviewer 的攻防和门禁写入中台铁三角架构。
- Diff Agent、证据冻结、候选法则、审核入库写入 Diff 流程架构。
- Workflow 步骤、暂停恢复、Tool 注册、权限审计和 Tool 事件写入工作流与 Tool 架构。
