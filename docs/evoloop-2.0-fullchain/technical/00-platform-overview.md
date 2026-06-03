# 00 平台总览

> 状态说明：本文档保留为 2.0 技术总览参考，不再是当前默认实现路线。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。
> 若本文与 3.0 文档冲突，以 3.0 文档为准。

## 1. 平台定位

Evoloop 2.0 是一个 AI 产品协作平台，核心价值不是“一次性生成文档”，而是把用户、多个专业 Agent、企业知识、任务产物和经验法则连接成持续进化的闭环。

平台由五条主线组成：

| 主线 | 目标 | 关键产物 |
|---|---|---|
| 任务执行线 | 把用户目标推进为可交付方案 | PRD、操作手册、技术方案等 Artifact |
| 共创交互线 | 让用户可观察、可打断、可接管 | DAG 透视窗、消息流、仲裁卡、接管表单 |
| 知识注入线 | 让 Agent 使用可信事实和历史法则 | GBrain query/search 结果、规则快照 |
| 经验学习线 | 从用户终稿中提炼可复用法则 | FrozenEvidence、CandidateRule、ApprovedRule |
| 治理审计线 | 确保权限、安全、可追溯 | ToolCall、Event、Checkpoint、Review Record |

## 2. 分层架构

```text
Presentation Layer
  前端工作台、任务大厅、知识库、法则审核页、Workspace 初始化向导

Platform Service Layer
  WorkspaceService、TaskService、ArtifactService、EvidenceService、RuleService、MaterialService

Agent Runtime Layer
  Main Orchestrator、Agent Registry、DAG Planner、Event Bus、Subagents、ToolPolicy

State & Knowledge Layer
  TaskContext、Blackboard、Checkpoint、GBrain MCP、Local Knowledge Snapshot

Storage Layer
  task.json、context.json、events.jsonl、artifacts、evidence、rule candidates、workspace config
```

## 3. 产品线关系

`manual`、`prd` 和未来的更多产品线不应该各自复制 orchestrator。它们应该被表达为不同的任务模板、输出规格和领域包组合。

```text
Product Line = Task Template + Output Spec + Domain Pack Requirements + Review Gates
```

| 产品线 | 任务模板 | 主要 Agent | 输出 |
|---|---|---|---|
| `prd` | `task_templates/prd.yaml` | Biz_Analyst、Tech_Critic、QA_Critic、Copywriter | `PRD.md` |
| `manual` | `task_templates/manual.yaml` | Material_Parser、Tech_Fact_Checker、QA_Operability、Copywriter | 操作手册 Markdown |
| `cloud_native_promotion` | `task_templates/cloud_native_promotion.yaml` | Biz_Analyst、Reliability_Guard、Observability_Architect、Deploy_Gen | 活动方案 + 运维清单 |

## 4. 平台级生命周期

```text
WorkspaceCreated
  -> DomainPackSelected
  -> TaskCreated
  -> DagPlanProposed
  -> DagPlanApproved
  -> TaskRunning
  -> ArtifactDraftCreated
  -> UserFinalSaved
  -> EvidenceFrozen
  -> DiffCandidatesReady
  -> RuleReviewed
  -> RuleStoredInGBrain
  -> TaskKnowledgeReusable
```

## 5. 非目标

- 不把 Evoloop 做成通用聊天机器人；所有协作都必须围绕 Task、Artifact、Rule 或 Workspace。
- 不在 PM-Agent 内自建知识基础设施；知识存储、检索、图谱和版本由 GBrain 提供。
- 不允许 Diff 自动修改当前任务产物；Diff 只学习，不回写本次交付。
- 不允许前端依赖 Python 日志、文件路径或内部 prompt。
