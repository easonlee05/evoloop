# 文档与规则流

当前仓库已经把“文档产物”和“规则卡片”拆成两条独立能力，但规则提炼仍是轻量实现。本文只描述现在已经存在的行为。

## 当前文档流

文档相关的实际链路如下：

```text
Writer 生成 artifact_content
  -> artifact.write 写入主文档
  -> 前端读取 /api/tasks/{task_id}/document
  -> 用户编辑文档
  -> PUT /api/tasks/{task_id}/document
  -> 后端备份旧 artifact
  -> 写入新版本内容
```

## 当前 artifact 行为

- 首次写入由 `artifact.write` Tool 完成。
- 读取文档使用 `GET /api/tasks/{task_id}/document` 或 `GET /api/artifacts/{artifact_id}`。
- 更新文档时，后端先执行 `backup_artifact`，再更新当前 artifact 内容。
- 如果内容未变化，`update_artifact` 会直接返回当前版本。

## 当前规则流

仓库里存在规则页面和对应接口：

- `GET /api/rules?status=pending|approved|rejected`
- `POST /api/rules/{rule_id}/approve`
- `POST /api/rules/{rule_id}/reject`

这些接口当前用于前端规则卡片展示和审核动作回传。

## 当前 diff 能力边界

`ToolService` 已注册 `diff.extract_rules`，但当前实现只返回候选结果占位：

```json
{
  "candidates": []
}
```

这表示当前系统已经为“从文档变化提炼规则”预留了统一入口，但运行时不会自动从编辑内容生成可信规则，也不会自动写入知识存储。

## 当前设计原则

- 文档保存是生产能力，必须稳定可用。
- 规则审核是独立页面能力，不与文档保存强绑定。
- 规则接口不暴露本地路径、原文文件或私有材料。
- artifact 备份先于覆盖写入，保证文档可回退、可追溯。
