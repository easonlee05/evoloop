# 05 GBrain 集成

## 1. 定位

GBrain 是 Evoloop 的长期知识基础设施。Evoloop/PM-Agent 不自建向量库、BM25、知识图谱、知识页版本或矛盾检测，而是通过 MCP Tool 调用 GBrain。

## 2. Source 规划

| Source | 用途 | 写入者 | 读取者 |
|---|---|---|---|
| `rules-global` | 全局强制法则 | RuleService 审核通过后 | 所有 Agent |
| `rules-domain` | 领域法则 | RuleService 审核通过后 | 对应 Domain Pack Agent |
| `knowledge-platform` | 平台事实、页面规则、字段定义 | 管理员/导入流程 | 所有 Agent |
| `knowledge-business` | 业务规则、流程、准入条件 | 管理员/材料审核流程 | 业务 Agent |
| `archive` | 废弃/归档法则 | RuleService 淘汰流程 | 管理员审计 |

## 3. Tool 封装

建议把 GBrain 能力注册为受控 Tool：

| Tool | 作用 | 允许调用者 |
|---|---|---|
| `knowledge.query` | 合成回答 + 引用 + gap analysis | Main Orchestrator、授权 Subagent |
| `knowledge.search` | 原始片段搜索 | 授权 Subagent、Diff_Extractor |
| `knowledge.get_page` | 读取指定知识页 | Reviewer、RuleService |
| `knowledge.find_contradictions` | 检测候选法则冲突 | Diff_Extractor、RuleService |
| `knowledge.put_page` | 写入审核通过的法则 | RuleService only |
| `knowledge.delete_page` | 归档/软删除法则 | RuleService 管理动作 |

关键约束：Subagent 不允许直接调用 `knowledge.put_page`。

## 4. 知识注入流程

```text
TaskCreated
  -> Orchestrator derives knowledge queries
  -> knowledge.query(rules-global + domain + business)
  -> GBrain returns answer/citations/gaps
  -> Blackboard.active_rules / knowledge_context
  -> ContextSlicer injects relevant snippets into node context
```

## 5. Gap Analysis

GBrain query 返回的 gap 应进入 Reviewer 和前端提示：

```text
knowledge_gaps
  - 缺少该模块最新 API 字段定义
  - 未找到该活动规则的退款口径
```

如果 gap 影响任务可信度，Reviewer 应阻断或要求用户补材料。

## 6. 降级策略

当 GBrain 不可用：

1. Tool 返回 `failed` 或 `degraded`，不得伪造成功。
2. Blackboard 标记 `knowledge_degraded=true`。
3. 使用本地最近一次安全快照。
4. Agent 输出附加降级提示。
5. Reviewer 增加“知识降级风险”检查。
6. Diff 候选仍可生成，但 conflict check 标记为 `degraded`，审核页必须提示用户。

## 7. 法则入库格式

审核通过的法则以 Markdown page 写入 GBrain：

```markdown
---
type: rule
scope: domain
protection: STANDARD
source_task: task_xxx
evidence_id: evidence_xxx
reviewed_by: user_xxx
reviewed_at: 2026-06-03T10:30:00Z
version: 1
---

# 所有对外 API 必须配置限流

当新增对外暴露的 API 端点时，必须在网关层配置限流策略。

## 证据来源

用户在终稿中补充了对外接口限流要求，AI 草稿遗漏该约束。
```
