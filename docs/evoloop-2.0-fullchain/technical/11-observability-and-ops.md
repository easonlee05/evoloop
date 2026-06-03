# 11 可观测与运维

## 1. 可观测目标

Evoloop 2.0 的运行过程长、Agent 多、LLM 成本高，因此必须从第一天记录可观测数据。

## 2. 指标

| 类别 | 指标 |
|---|---|
| 任务 | 创建数、完成率、失败率、平均耗时、等待用户时长 |
| DAG | 节点耗时、节点失败率、重试次数、stale 重跑次数 |
| LLM | 调用次数、token、耗时、失败率、预算熔断次数 |
| Tool | 调用次数、denied 数、失败率、外部依赖耗时 |
| GBrain | query/search 延迟、降级次数、冲突检测耗时 |
| Diff | evidence 数、candidate 数、通过率、驳回率、低置信候选数 |
| 前端 | SSE 断线率、重新连接次数、用户接管次数 |

## 3. 事件回放

事件是恢复和审计的核心，不是 UI 附属物。

```text
events.jsonl
  -> API replay
  -> frontend rebuild timeline
  -> ops audit
  -> debugging
```

事件必须 append-only；修正状态通过新事件表达。

## 4. 失败恢复

| 失败点 | 恢复策略 |
|---|---|
| LLM 调用失败 | 节点重试，超限后 blocked 或请求用户接管。 |
| Tool denied | 不重试，展示权限问题。 |
| GBrain 不可用 | 使用快照降级，标记 knowledge_degraded。 |
| SSE 断开 | 前端重连并从事件回放恢复。 |
| Diff 失败 | 主任务保持 completed/final_saved，Diff 可重试。 |
| Rule 入库失败 | Candidate 保持 approved_pending_store 或 store_failed。 |

## 5. 成本预算

SessionBudget 应覆盖：

- max_hops。
- max_llm_calls。
- max_tokens。
- max_wall_clock_seconds。
- max_tool_calls_per_node。

预算超限事件应进入前端和审计。

## 6. 本地开发与生产差异

| 能力 | 本地开发 | 生产 |
|---|---|---|
| GBrain | stdio MCP 或 fake backend | HTTP MCP + OAuth |
| Storage | 文件系统 JSON | DB/Object Storage |
| Event Bus | in-memory queue | Redis/NATS/Kafka 可选 |
| LLM | 环境变量配置 | Secret manager |
| Artifact | 本地文件 | 对象存储 + DB metadata |
