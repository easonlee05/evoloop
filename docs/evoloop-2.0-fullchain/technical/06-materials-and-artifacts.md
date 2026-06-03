# 06 材料与产物

## 1. 材料库

材料库接收用户上传的文件、截图、链接或文本片段，但上传不等于可信知识入库。

```text
Material
  material_id
  workspace_id
  uploader
  filename
  content_type
  storage_ref
  safe_summary
  parse_status
  created_at
```

## 2. 材料解析

材料解析通过 `material.parse` Tool 完成：

```text
Upload Material
  -> material.uploaded
  -> material.parse.started
  -> parser extracts safe text / OCR / metadata
  -> material.parse.completed
  -> parsed_material_package
```

解析结果只能作为当前任务上下文或候选知识来源，不能直接写入 GBrain trusted sources。

## 3. Artifact 模型

Artifact 是任务可交付产物。它必须版本化，并区分 AI 草稿、用户编辑版本和终稿。

```text
Artifact
  artifact_id
  task_id
  workspace_id
  name
  version
  content_type
  created_by
  status: draft | user_edited | final
  content_ref
  previous_version_id
  summary
  created_at
```

## 4. 写入规则

- Writer 只能通过 `artifact.write` 写草稿。
- 用户编辑前必须 `artifact.backup`。
- 同名写入不能静默丢弃新内容，必须创建版本或返回幂等结果。
- 终稿保存必须显式动作，不等于普通 auto-save。

## 5. 终稿保存

建议新增语义明确的终稿 API：

```text
POST /api/tasks/{task_id}/save-final
  body:
    artifact_id
    content
    finalize_reason
```

后端处理：

```text
1. backup current artifact
2. update artifact content
3. mark artifact.status = final
4. emit artifact.final_saved
5. call EvidenceService.freeze(task_id, artifact_id)
6. trigger diff_extraction post-task DAG
```

普通编辑器 auto-save 只调用 document update，不触发 Diff 学习。

## 6. Artifact 与 Evidence 的关系

Evidence 冻结时复制必要快照，而不是引用可变 artifact 当前内容。

```text
AI draft artifact v1
User final artifact v3
  -> FrozenEvidence stores immutable snapshots
  -> later artifact v4 edits do not mutate old evidence
```

## 7. 安全要求

- API 响应不得暴露服务器绝对路径。
- 原始材料正文默认不进入 SSE payload。
- Artifact 内容可通过授权 API 读取，但事件只传摘要和 artifact_id。
- 删除任务不能直接永久删除 evidence 和 approved rule 的审计引用。
