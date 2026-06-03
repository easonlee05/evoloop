# Evoloop 2.0 Architecture

> 状态说明：本目录保留为 2.0 历史架构参考，不再是当前目标架构真相源。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。
> 若 2.0 与 3.0 文档冲突，以 3.0 为准。

本目录是 Evoloop 2.0 的详细架构设计集，颗粒度对齐 `docs/architecture-v2/`，但覆盖范围从 PM-Agent 内核扩展到了整个 Evoloop 平台。

## 文档索引

| 编号 | 文档 | 主题 |
|---|---|---|
| 00 | `00-global-architecture.md` | 全局分层、主链路、对象模型、平台边界 |
| 01 | `01-workspace-and-domain-architecture.md` | Workspace、领域包、扩展包、RuntimeProfile |
| 02 | `02-agent-runtime-architecture.md` | Main Orchestrator、Registry、MessageEnvelope、Tool 边界 |
| 03 | `03-dag-orchestration-architecture.md` | TaskDAG、DAGValidator、Plan-then-Execute、后置 DAG |
| 04 | `04-state-and-context-architecture.md` | TaskContext、Blackboard、MergePolicy、Checkpoint、DirtyPropagation |
| 05 | `05-knowledge-and-gbrain-architecture.md` | GBrain source、知识注入、gap、降级、规则入库边界 |
| 06 | `06-artifact-and-evidence-architecture.md` | Artifact lineage、终稿保存、EvidenceService、FrozenEvidence |
| 07 | `07-diff-and-rule-learning-architecture.md` | 语义 Diff、CandidateRule、RuleService、审核与生命周期 |
| 08 | `08-frontend-collaboration-architecture.md` | 工作台、SSE 透视窗、Takeover、终稿与规则审核体验 |
| 09 | `09-platform-api-and-event-architecture.md` | 平台 API 分组、事件分层、回放与兼容策略 |
| 10 | `10-security-and-governance-architecture.md` | ToolPolicy、多租户、安全、Pack 治理、审计 |
| 11 | `11-observability-and-operations-architecture.md` | 指标、回放、恢复、预算、降级与生产运维 |

## 建议阅读顺序

1. 先读 `00-global-architecture.md` 建立总图。
2. 再读 `01` 到 `05` 理解运行时与知识边界。
3. 再读 `06` 到 `09` 串联交付、终稿、Diff、前端和 API。
4. 最后读 `10` 和 `11` 看治理与运维。

`../technical/` 目录存放实现与落地文档，不替代这里的架构边界。
