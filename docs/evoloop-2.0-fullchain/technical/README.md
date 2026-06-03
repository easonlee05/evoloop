# Evoloop 2.0 Technical

> 状态说明：本目录保留为 2.0 历史技术参考，不再是当前实现目标默认路线。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。
> 若 2.0 与 3.0 文档冲突，以 3.0 为准。

本目录存放 Evoloop 2.0 的技术落地文档，用于承接实现层说明、接口草案、工程约束和迁移路线。

它与 `../architecture/` 的关系是：

- `architecture/` 解释系统为什么这样分层、边界如何划分。
- `technical/` 解释这些边界在实现中如何落地。

## 当前内容

| 文档 | 说明 |
|---|---|
| `00-platform-overview.md` | 平台技术总览摘要版 |
| `01-workspace-domain-packs.md` | Workspace 与领域包的实现导向说明 |
| `02-agent-runtime.md` | Agent Runtime 的技术说明版 |
| `03-dag-orchestration.md` | DAG 编排的技术说明版 |
| `04-state-and-context.md` | 状态与上下文的技术说明版 |
| `05-knowledge-gbrain.md` | GBrain 接入的技术说明版 |
| `06-materials-and-artifacts.md` | 材料、Artifact、终稿的技术说明版 |
| `07-diff-rule-learning.md` | Diff 与规则学习的技术说明版 |
| `08-frontend-collaboration.md` | 前端协作的技术说明版 |
| `09-api-event-contract.md` | API 与事件契约草案 |
| `10-security-and-governance.md` | 安全与治理技术说明 |
| `11-observability-and-ops.md` | 可观测与运维说明 |
| `12-implementation-roadmap.md` | 分阶段实现路线 |

后续如果某一篇 technical 文档与 architecture 文档重复，应以 architecture 为边界真相，以 technical 为实现补充。
