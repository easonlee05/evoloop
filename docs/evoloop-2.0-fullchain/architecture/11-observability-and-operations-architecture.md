# 11 可观测与运维架构

## 1. 为什么 Evoloop 2.0 更需要可观测

Evoloop 2.0 相比普通 CRUD 系统有三层额外复杂度：

- LLM 调用成本高且不稳定。
- 多 Agent 协作可能带来链路长、失败点多。
- 用户看到的是“过程”，而不仅是最终结果。

因此平台必须设计成天然可观测，而不是靠事后加日志。

## 2. 可观测对象

### 2.1 任务层

- 任务创建数
- 完成率
- 等待用户时长
- 主任务成功率

### 2.2 DAG 层

- 节点执行耗时
- 并行节点数
- stale 节点重跑率
- blocked / failed 节点比例

### 2.3 Agent 层

- 每个 Slot 的调用次数
- 输出 schema 失败率
- 平均 token 成本
- takeover 命中率

### 2.4 Tool 层

- Tool 调用成功率
- denied 率
- 外部依赖耗时
- GBrain 降级次数

### 2.5 学习层

- evidence 生成数
- candidate rule 数
- approve/reject 比例
- store_failed 次数

## 3. 事件回放作为诊断基础设施

`events.jsonl` 不是“给前端看的日志文件”，而是：

- 前端状态恢复依据
- 运维诊断依据
- 失败复盘依据
- 审计查询依据

因此事件必须 append-only，并且保证顺序可恢复。

## 4. 检查点与恢复

平台恢复依赖于三件事：

1. 当前 `task.json`
2. 最近 checkpoint
3. 事件尾部回放

恢复策略：

```text
load task
  -> load latest checkpoint
  -> rebuild blackboard and node states
  -> replay tail events if needed
  -> continue from waiting/pending nodes
```

## 5. 成本控制

SessionBudget 不只是防死锁，也服务于运营控制：

- 限制某个节点的最大 LLM 次数
- 限制一个 task run 的最大 token
- 限制某些 post-task learning DAG 的预算

预算耗尽不应该是静默失败，而应成为显式事件与可见状态。

## 6. 降级运维

### 6.1 GBrain 降级

当知识层不可用时：

- 使用本地快照
- 前端显示知识降级
- Reviewer gate 增加风险检查

### 6.2 LLM 服务降级

当模型服务异常时：

- 尝试切换到 fallback provider 或减少并行度
- 节点进入 retry 或 blocked
- 避免把整个任务误判为 completed

### 6.3 Diff 服务降级

Diff 失败不影响主任务，只标记学习链路可重试。

## 7. 本地与生产形态

### 7.1 本地

- FakeStorage / 文件系统
- 本地 uvicorn
- stdio MCP 或 fake GBrain
- 内存 Event Bus

### 7.2 生产

- DB + 对象存储
- HTTP MCP + OAuth
- 持久化消息队列
- 统一 metrics / tracing / audit pipeline

## 8. 运维边界

运维层要观察的是平台健康，而不是业务 prompt 内容。因此建议采集：

- 状态码
- 事件类型
- 耗时
- 节点数
- tokens
- retries
- denied / failed counts

而不要采集：

- 原始 prompt
- 用户隐私材料全文
- 整篇规则页面全文

## 9. 对实现的约束

如果一个新功能不能回答以下问题，就说明它还没达到 Evoloop 2.0 的运维要求：

1. 它的状态从哪里恢复？
2. 它失败后如何重试？
3. 它会发出哪些结构化事件？
4. 它如何区分用户错误、权限错误和系统错误？
5. 它对主任务交付是否是强依赖？
