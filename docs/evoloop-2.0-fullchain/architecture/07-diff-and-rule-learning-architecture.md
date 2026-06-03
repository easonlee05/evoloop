# 07 Diff 与规则学习架构

## 1. 设计定位

Evoloop 的长期价值不在“这次写出一份文档”，而在“下次更懂这个团队的真实约束”。Diff 与规则学习架构正是这条经验飞轮。

其目标是：

- 从用户真实修改中学习。
- 把一次性偏好与可复用规则区分开。
- 保证学习过程不污染当前主任务。
- 让人工审核成为可信规则入库的闸门。

## 2. 为什么 Diff 不能混进主任务 DAG

主任务的目标是交付；Diff 的目标是学习。它们在触发时机、输入、失败语义和用户交互模式上都不同。

| 维度 | 主任务 | Diff Learning |
|---|---|---|
| 触发 | 任务创建/运行 | 用户终稿保存后 |
| 输入 | 目标、材料、知识、黑板状态 | AI 草稿、终稿、审查与裁决记录 |
| 输出 | 文档 Artifact | CandidateRule |
| 失败影响 | 影响交付 | 不影响交付 |
| 用户交互 | 仲裁、接管、暂停 | 规则审核 |

因此 Diff 应作为独立后置 DAG 存在。

## 3. Diff 学习流水线

```text
save-final
  -> freeze evidence
  -> compute semantic diff hunks
  -> extract candidate rules
  -> detect duplicates/conflicts
  -> publish candidates
  -> user review
  -> approved rule stored in GBrain
```

## 4. Semantic Diff

### 4.1 为什么不能只用 unified diff

文档重排、同义替换、标题调整会制造大量噪音，无法直接得到“规则级变化”。

Diff 学习要识别的是语义差异：

- 是否补充了前置条件。
- 是否删除了 AI 幻觉。
- 是否增加了异常链路。
- 是否把软建议改成硬约束。
- 是否补充了验收标准、审计要求、指标口径。

### 4.2 DiffHunk 模型

```text
DiffHunk
  hunk_id
  location
  ai_content
  user_content
  change_type
  semantic_type
  is_substantive
  explanation
```

`semantic_type` 建议包括：

- `missing_constraint`
- `hallucination_removed`
- `exception_flow_added`
- `acceptance_added`
- `metric_clarified`
- `scope_narrowed`
- `wording_only`

## 5. CandidateRule 抽取

Diff_Extractor 的职责不是生成最终规则，而是生成“待审核候选”。

### 5.1 CandidateRule 模型

```text
CandidateRule
  rule_id
  workspace_id
  task_id
  evidence_id
  source_hunk_ids[]
  rule_title
  rule_content
  evidence_summary
  suggested_scope
  suggested_protection
  confidence
  duplicate_of[]
  has_conflicts
  conflict_details[]
  review_status
```

### 5.2 低置信候选

低置信候选不应自动进入主审核流，以免把大量噪音推给用户。更好的做法是：

- 默认隐藏或折叠。
- 允许用户主动展开查看。
- 在后端保留，供后续合并或分析。

## 6. Diff_Extractor 作为运行时角色

Diff_Extractor 属于 Core Pack 的附加能力，但它不属于主任务执行拓扑。

它只能：

- 读取 `FrozenEvidence`
- 使用 `knowledge.search`
- 使用 `knowledge.find_contradictions`

它不能：

- 写 Artifact
- 写 GBrain
- 修改主任务状态

## 7. RuleService 治理层

RuleService 是 Diff 学习和 GBrain 之间的中间治理层。

它负责：

- 持久化 CandidateRule。
- 管理审核状态。
- 对接冲突检测。
- 组装最终 rule page。
- 调用 GBrain 写入 approved rule。
- 负责 archive/eviction 的平台决策逻辑。

它不负责：

- 直接生成文档差异。
- 直接解释用户意图。
- 代替用户审核。

## 8. 审核动作语义

### 8.1 approve

原候选内容按建议参数入库。

### 8.2 modify_and_approve

用户编辑后入库，但必须保留：

- 原候选内容
- 用户修改内容
- evidence_id
- reviewer identity

### 8.3 scope_and_approve

用户调整适用范围，例如把 `domain` 收窄为 `scenario`。

### 8.4 reject

标记 rejected，不写入 GBrain，但候选记录保留供审计。

## 9. 冲突与重复检测

### 9.1 重复

如果 CandidateRule 与现有规则实质相同，应提示：

- 推荐关联已有规则，而不是重复入库。
- 或合并为新版本。

### 9.2 冲突

若候选规则与 `rules-global` 冲突，应阻止一键入库，并强制显示冲突详情。

冲突分级建议：

- `hard_conflict`
- `soft_conflict`
- `needs_scope_narrowing`

## 10. 规则生命周期

规则的生命周期不是“approve 之后就结束”，而是：

```text
candidate
  -> approved
  -> active
  -> low-hit / stale
  -> archived
```

平台的 RuleService 负责决策何时归档；GBrain 负责存储与检索。

## 11. 事件架构

Diff 与 Rule Learning 应至少产生以下事件：

- `evidence.freeze.started`
- `evidence.frozen`
- `diff.hunks.computed`
- `diff.extraction.started`
- `diff.candidates_ready`
- `diff.extraction.failed`
- `rule.review.started`
- `rule.approved`
- `rule.rejected`
- `rule.stored`
- `rule.store.failed`

这些事件必须是前端和审计都能消费的结构化事件。

## 12. 失败语义

### 12.1 Diff 失败

不影响主任务交付状态，只影响知识学习。

### 12.2 审核失败

CandidateRule 保持在 pending 或进入 store_failed，不应 silently 丢失。

### 12.3 GBrain 写入失败

应记录：

- candidate id
- final rule payload summary
- 失败原因
- 可重试状态

这样可以后续重放写入，而不需要重新跑一遍 Diff 提炼。
