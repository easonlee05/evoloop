# Evoloop 2.0 Fullchain

> 状态说明：本目录保留为 2.0 历史架构参考，不再是当前目标架构真相源。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。

本目录拆成两层：

- `architecture/`：面向产品和系统边界的详细架构设计，颗粒度对齐 `docs/architecture-v2/`。
- `technical/`：面向实现落地的技术文档、API 契约、工程路线、材料/产物/Diff 细节。

## 目录说明

```text
docs/evoloop-2.0-fullchain/
  README.md
  architecture/
  technical/
```

## 阅读顺序

1. `architecture/00-global-architecture.md`
2. `architecture/01-workspace-and-domain-architecture.md`
3. `architecture/02-agent-runtime-architecture.md`
4. `architecture/03-dag-orchestration-architecture.md`
5. `architecture/04-state-and-context-architecture.md`
6. `architecture/05-knowledge-and-gbrain-architecture.md`
7. `architecture/06-artifact-and-evidence-architecture.md`
8. `architecture/07-diff-and-rule-learning-architecture.md`
9. `architecture/08-frontend-collaboration-architecture.md`
10. `architecture/09-platform-api-and-event-architecture.md`
11. `architecture/10-security-and-governance-architecture.md`
12. `architecture/11-observability-and-operations-architecture.md`

`technical/` 目录作为这些架构文档的实现补充，不替代架构边界本身。
