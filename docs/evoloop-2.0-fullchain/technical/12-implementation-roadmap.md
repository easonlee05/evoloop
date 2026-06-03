# 12 落地路线

本路线只描述架构和技术落地顺序，不要求一次性重写现有代码。目标是从 Phase 1 固定 workflow 平滑演进到 Evoloop 2.0 全链路。

## Phase 0：文档与契约对齐

- 建立本目录作为 Evoloop 2.0 全链路架构入口。
- 将 `docs/architecture-v2/07-diff-extraction-pipeline.md` 纳入 v2 总索引。
- 更新 `docs/refactor/api-contract.md`，补充终稿保存、Diff、RuleCandidate、DAG plan、Takeover API。
- 明确 `TaskDefinition` 到 `TaskDAG` 的迁移边界。

## Phase 1：Diff MVP

目标：先把经验闭环跑通，不阻塞主任务。

新增或补充：

```text
app/core/evidence.py
app/core/rules.py
app/services/evidence_service.py
app/services/rule_service.py
app/services/diff_service.py
```

能力：

1. 用户保存终稿。
2. 冻结 AI 草稿和用户终稿。
3. 计算基础 DiffHunk。
4. 生成 CandidateRule。
5. RuleAudit 审核 pending candidates。
6. approved 先落本地，再接 GBrain。

## Phase 2：GBrain Tool 化

- 增加 `app/tools/gbrain_mcp_client.py`。
- 增加 `app/tools/knowledge_tool.py`。
- 注册 `knowledge.query/search/find_contradictions/put_page`。
- RuleService approve 后写入 GBrain。
- GBrain 降级时保存候选，但标记 conflict check degraded。

## Phase 3：Agent Runtime 内核

新增：

```text
app/core/envelope.py
app/core/registry.py
app/core/dag.py
app/core/blackboard.py
app/core/context_slicer.py
app/core/merge_engine.py
app/core/session_budget.py
app/agents/base.py
```

目标：不依赖真实 LLM 也能通过单元测试验证 DAG、Registry、Blackboard 和 Budget。

## Phase 4：Task Template 迁移

- 新增 `task_templates/prd.yaml`。
- 新增 `task_templates/manual.yaml`。
- 将现有 `app/workflows/prd.py` 和 `manual.py` 逐步迁移为模板。
- TaskService 对外 API 不变，内部从 WorkflowSpec 切到 TaskDAG。

## Phase 5：前端共创升级

- Workspace 初始化向导。
- DAG 计划展示和确认。
- Takeover 表单。
- 终稿保存按钮。
- Diff 学习状态提示。
- RuleCandidate 审核卡片支持 scope/protection/conflict。

## Phase 6：治理和生产化

- Workspace 租户隔离。
- 扩展包签名或 trust level。
- 审计查询。
- 指标采集。
- 生产存储替换本地 JSON。
- Rule lifecycle 淘汰和归档。

## 关键验收标准

- 主任务完成不依赖 Diff 成功。
- Diff Agent 永远不能直接写 GBrain。
- 用户终稿和 evidence 不会被后续 artifact 编辑篡改。
- CandidateRule 审核通过后，后续任务能从 GBrain 检索到对应法则。
- 前端刷新后能通过事件回放恢复任务、DAG、Diff 和 Rule 状态。
