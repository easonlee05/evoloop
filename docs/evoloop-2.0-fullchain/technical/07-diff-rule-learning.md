# 07 Diff 与法则学习

## 1. 定位

Diff 是 Evoloop 的经验飞轮。它不修改当前交付，而是在用户保存终稿后，从“AI 草稿 -> 用户终稿”的差异中提炼可复用的候选法则。

```text
主任务交付方案
  -> 用户编辑并保存终稿
  -> EvidenceService 冻结证据
  -> Diff Extraction DAG 提炼 CandidateRule
  -> RuleAudit 人工审核
  -> RuleService 写入 GBrain
  -> 后续任务检索复用
```

## 2. 为什么 Diff 是独立后置 DAG

| 维度 | 主任务 DAG | Diff DAG |
|---|---|---|
| 目标 | 交付当前方案 | 学习可复用经验 |
| 触发 | 用户创建任务 | 用户保存终稿 |
| 输入 | 目标、材料、知识、上下文 | AI 草稿、用户终稿、仲裁/审查记录 |
| 失败影响 | 影响本次交付 | 不影响本次交付 |
| 用户参与 | 旁听、打断、接管、仲裁 | 审核候选法则 |

## 3. FrozenEvidence

```text
FrozenEvidence
  evidence_id
  task_id
  workspace_id
  frozen_at
  task_type
  domain_pack
  ai_draft_snapshot
  user_final_snapshot
  diff_hunks[]
  arbitration_records[]
  reviewer_records[]
  knowledge_rule_snapshot[]
  artifact_version_pair
```

证据一旦冻结不可修改；用户后续再次编辑会产生新的 evidence。

## 4. DiffHunk

```text
DiffHunk
  hunk_id
  location
  ai_content
  user_content
  change_type: addition | deletion | modification | move
  semantic_type: missing_constraint | hallucination_removed | exception_added | acceptance_added | wording_only | other
  is_substantive
  reason
```

只将 `is_substantive=true` 的 hunk 送入候选法则提炼。

## 5. 语义 Diff 流程

```text
split markdown into sections
  -> align sections by heading and similarity
  -> detect additions/deletions/modifications/moves
  -> classify semantic type
  -> filter wording_only and reorder-only changes
  -> produce substantive DiffHunks
```

实质性修改包括：

- 用户补充业务前置条件。
- 用户删除 AI 瞎编的平台事实。
- 用户补齐异常流程、降级策略、审计要求。
- 用户补充验收标准或指标口径。
- 用户把通用建议改成领域强约束。

非实质性修改包括：

- 纯润色。
- 标点和格式调整。
- 段落重排但内容不变。
- 单次任务特例且无法泛化。

## 6. CandidateRule

```text
CandidateRule
  rule_id
  workspace_id
  source_task_id
  evidence_id
  source_diff_hunk_id
  rule_title
  rule_content
  evidence_summary
  suggested_scope: global | domain | module | scenario
  suggested_protection: CRITICAL | STANDARD
  confidence: high | medium | low
  has_conflicts
  conflict_details[]
  duplicate_candidates[]
  review_status: pending | approved | modified | rejected
  created_at
```

低置信度候选默认不推送到主审核流，可进入“低置信候选”列表供用户主动查看。

## 7. Diff_Extractor 权限

允许：

- `knowledge.search`
- `knowledge.find_contradictions`
- `artifact.read` 或读取 frozen evidence 中的快照

禁止：

- `artifact.write`
- `knowledge.put_page`
- 任意 shell / 网络 / 原始路径读取

## 8. RuleService

RuleService 是候选法则的治理层：

```text
RuleService
  create_candidates(evidence, extractor_output)
  list_candidates(status, workspace_id)
  approve(rule_id, reviewer, edited_content, scope, protection)
  reject(rule_id, reviewer, reason)
  detect_conflicts(rule)
  store_to_gbrain(rule)
  archive_rule(rule_id)
```

RuleService 负责 PM-Agent 侧决策逻辑；GBrain 负责长期存储和检索。

## 9. 审核动作

| 动作 | 结果 |
|---|---|
| approve | 原候选内容按建议 scope/protection 入库。 |
| modify_and_approve | 用户编辑标题/内容后入库，保留原候选和修改记录。 |
| scope_and_approve | 用户调整作用域或保护等级后入库。 |
| reject | 标记 rejected，不写入 GBrain。 |

## 10. 事件

```text
artifact.final_saved
evidence.freeze.started
evidence.frozen
diff.extraction.started
diff.hunks.computed
diff.candidates_ready
diff.extraction.failed
rule.review.started
rule.approved
rule.rejected
rule.stored
rule.store.failed
```

## 11. API 建议

```text
POST /api/tasks/{task_id}/save-final
GET  /api/tasks/{task_id}/evidence
GET  /api/diff/tasks/{task_id}/candidates
GET  /api/rules/candidates?status=pending
POST /api/rules/candidates/{rule_id}/review
GET  /api/rules/approved
```

旧的 `/api/rules/{rule_id}/approve` 可以保留兼容，但 v2 应以 candidate review API 为准。
