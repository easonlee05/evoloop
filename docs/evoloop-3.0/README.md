# Evoloop 3.0

本目录是 Evoloop 3.0 的主架构入口。

3.0 的目标不是继续把 Evoloop 做成“文档生成平台”，而是把它定义为一个数字产品经理系统：

- 上游接收业务目标、材料、反馈和用户裁决
- 中间编译为结构化 spec、agent package 和 acceptance protocol
- 下游协调 Codex、Claude Code、Cursor 等 AI worker
- 最后按需求和验收协议回收结果，并沉淀长期产品记忆

## 与 1.0 / 2.0 的关系

- `1.0`：现有可运行代码基线，仍以 `manual` / `prd` 工作流为主。
- `2.0`：重要的架构草稿库，保留了 DAG、Blackboard、Artifact/Evidence、治理等高价值抽象，但不再是当前目标产品定义。
- `3.0`：当前真相源。后续实现、重构、API 演进和 AI tool routing 都应以本目录为准。

## 重要约束

- `docs/evoloop-2.0-fullchain/` 和 `docs/vision/pm_agent_v2_vision.md` 仅作历史参考。
- 若 2.0 与 3.0 文档冲突，以 3.0 为准。
- 若现有代码仍停留在 1.0 形态，以 3.0 目标为重构方向，而不是先补完 2.0。

## 建议阅读顺序

1. `architecture/00-global-architecture.md`
2. `technical/00-evolution-roadmap.md`
3. `technical/01-parallel-development-boundaries.md`
4. `technical/02-contracts-minimum-boundaries.md`
5. `technical/04-engineering-evolution.md`
