# 06 Artifact 与 Evidence 架构

## 1. 为什么 Artifact 与 Evidence 要分开

在 Evoloop 2.0 中，文档产物和学习证据不是同一层对象。

- `Artifact` 面向交付与编辑，是用户当前要看的文档。
- `FrozenEvidence` 面向学习与审计，是终稿某个时刻的不可变快照。

如果二者混用，会导致：

- 用户后续改文档时篡改历史证据。
- Diff 学习拿不到稳定对比基线。
- 审计无法追踪“当时审核通过的到底是哪一版”。

## 2. Artifact 模型

```text
Artifact
  artifact_id
  task_id
  workspace_id
  name
  version
  status: draft | user_edited | final
  content_type
  created_by
  content_ref
  previous_version_id
  summary
  created_at
  updated_at
```

### 2.1 Artifact 的三种角色

1. AI 草稿：由 Writer 节点生成，代表系统当前交付候选。
2. 用户编辑版：用户在编辑器中修改后的工作版本。
3. 终稿版：用户显式确认的冻结交付版本。

## 3. Artifact 生命周期

```text
writer writes draft
  -> draft artifact
  -> user edits
  -> backup previous version
  -> user_edited artifact
  -> user clicks save-final
  -> final artifact
```

自动保存和终稿保存必须区分，因为它们触发的后续动作不同。

## 4. Artifact Service 的职责

ArtifactService 负责：

- 创建和更新版本。
- 提供读取接口。
- 在写入前备份上一版本。
- 维护 artifact lineage。
- 标记 `final` 状态。

它不负责：

- 提炼法则。
- 做知识冲突检测。
- 直接写 GBrain。

## 5. Writer 输出与 Artifact 持久化解耦

Writer 节点输出的是“候选内容”，真正写入由 Artifact 节点或 ArtifactService 负责。

```text
Writer node
  -> outputs artifact_content

Artifact node
  -> artifact.write(name, content)
  -> persist versioned artifact
```

这样可以保证：

- Writer 无法绕过版本规则。
- Artifact 写入有统一审计。
- 后续可以插入模板渲染、格式校验、备份策略。

## 6. 终稿保存

终稿保存必须是显式语义动作：

```text
POST /api/tasks/{task_id}/save-final
```

处理顺序建议固定为：

1. 备份当前 Artifact。
2. 写入新版本内容。
3. 标记该版本为 `final`。
4. 记录 `artifact.final_saved` 事件。
5. 调用 EvidenceService 冻结证据。
6. 触发 post-task `diff_extraction` DAG。

## 7. FrozenEvidence 模型

```text
FrozenEvidence
  evidence_id
  task_id
  workspace_id
  artifact_pair
    ai_draft_artifact_id
    final_artifact_id
  ai_draft_snapshot
  final_snapshot
  arbitration_records[]
  reviewer_records[]
  active_rule_snapshot[]
  diff_hunks[]
  created_at
```

其中 `snapshot` 必须是内容拷贝而非可变引用。

## 8. Evidence Service

EvidenceService 是终稿学习链路的桥梁。它的职责：

- 读取当前任务的 AI 草稿和终稿。
- 汇总 Reviewer 与 arbitration 记录。
- 调用 diff 预处理生成 `DiffHunk[]`。
- 生成不可变 `FrozenEvidence`。
- 发出 `evidence.freeze.started` 与 `evidence.frozen` 事件。

它不负责：

- 提炼 CandidateRule。
- 审核规则。
- 写入 GBrain。

## 9. Evidence 与 Artifact 的关系

```text
Artifact v1 (AI draft)
Artifact v2 (user edits)
Artifact v3 (final)
  -> Evidence e1 stores snapshots of v1 and v3

Artifact v4 (later edits)
  -> must not mutate e1
  -> may create e2 when final saved again
```

## 10. 删除与保留策略

Artifact 可随任务一起删除或归档，但一旦某个 Artifact 被 Evidence 或 Approved Rule 引用，就不能无痕硬删除。

建议：

- Task 删除：软删除任务和普通 artifact。
- Evidence 引用中的 artifact：保留审计快照。
- Approved Rule 引用证据：至少保留 evidence 摘要和版本元信息。

## 11. 与 Diff 的衔接边界

Artifact/Evidence 层只负责提供：

- 哪一版是 AI 草稿。
- 哪一版是最终用户确认稿。
- 当时的上下文证据是什么。

Diff 层只消费这些输入，并输出 CandidateRule，不回写 Artifact 内容。
