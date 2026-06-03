# 05 知识与 GBrain 架构

## 1. 知识层定位

Evoloop 2.0 需要一个稳定的长期知识底座，但这个底座不应当由 PM-Agent 自建。GBrain 已经具备：

- 检索与排序
- 知识页版本
- 冲突检测
- 多 source 隔离
- 长期存储与归档

因此 Evoloop 对 GBrain 的定位是：长期知识基础设施，而非任务运行时的一部分。

## 2. 三类知识

### 2.1 平台事实

页面规则、字段定义、系统能力边界，变化频率相对较低。

### 2.2 业务知识

业务流程、准入条件、上下游约束、运营口径。

### 2.3 可信法则

来自任务终稿学习并经人工审核通过的经验规则。它是 Evoloop 长期价值沉淀的核心。

## 3. GBrain Source 规划

```text
rules-global
rules-domain
knowledge-platform
knowledge-business
archive
```

每类 source 的职责要明确：

| Source | 职责 |
|---|---|
| `rules-global` | 全局强制规则，如合规、安全红线。 |
| `rules-domain` | 领域规则，如云原生/电商特化经验。 |
| `knowledge-platform` | 平台事实。 |
| `knowledge-business` | 业务材料或管理员整理后的业务知识。 |
| `archive` | 已废弃规则，仅用于审计。 |

## 4. 为什么不能把 GBrain 当运行时黑板

GBrain 和 Blackboard 的职责完全不同：

| 维度 | Blackboard | GBrain |
|---|---|---|
| 生命周期 | 单次 DAG run | 跨任务长期存在 |
| 更新频率 | 高频、每次节点 merge | 低频、审核后写入 |
| 数据性质 | 临时共识与工作状态 | 长期知识 |
| 冲突处理 | MergePolicy / arbitration | 知识冲突检测与规则治理 |

如果把两者混成一个系统，任务执行和长期知识将互相污染。

## 5. GBrain 接入层

Evoloop 通过 MCP Tool 封装接入 GBrain，而不是把 GBrain SDK 直接散落在业务逻辑中。

```text
KnowledgeTool
  query()
  search()
  get_page()
  find_contradictions()
  put_page()
  delete_page()
```

这层封装的职责：

- 统一错误处理。
- 统一审计和事件。
- 屏蔽 stdio/HTTP 差异。
- 让 ToolPolicy 可以显式控制谁能用哪些能力。

## 6. 知识注入路径

### 6.1 任务初始化阶段

Main Orchestrator 根据任务目标和领域包生成初始 query，把结果写入 Blackboard：

```text
goal + task_type + domain_pack
  -> knowledge.query/search
  -> knowledge_context
  -> active_rules
  -> knowledge_gaps
```

### 6.2 节点执行阶段

Context Slicer 根据 SlotContract 所需字段，为节点注入相关知识摘要和引用，而不是把整份 query answer 全量透传。

### 6.3 规则审核阶段

RuleService 使用 `find_contradictions` 检测候选规则与现有规则是否冲突，再决定是否允许写入。

## 7. Gap Analysis

GBrain 返回的 gap 不是附属信息，而是运行时控制信号：

- 若 gap 轻微：节点继续执行，但标记不确定性。
- 若 gap 影响核心方案：Reviewer gate 必须阻断。
- 若 gap 来自缺材料：前端提示用户补材料。

## 8. 法则入库路径

```text
CandidateRule approved
  -> RuleService formats final rule page
  -> knowledge.find_contradictions
  -> if safe: knowledge.put_page
  -> persist gbrain slug and version
```

关键原则：

- 写入动作只能由审核流程发起。
- Diff Agent 不能直接写入 GBrain。
- 用户修改后的 rule 内容也必须保留与 evidence 的绑定。

## 9. 降级策略

### 9.1 GBrain 不可用

系统应：

1. 返回结构化降级结果。
2. 使用最近一次可信快照。
3. 在 Blackboard 中标记 `knowledge_degraded=true`。
4. 在 Reviewer 阶段增加知识风险门禁。

### 9.2 冲突检测不可用

候选规则仍可进入审核，但必须标记：

```text
conflict_check_status = degraded
```

前端禁止用“绿色通过”样式伪装成正常状态。

## 10. 与材料库的关系

材料上传并不直接进入 GBrain trusted source。材料需要：

```text
upload
  -> parse
  -> optional candidate knowledge
  -> manual/admin approval
  -> then enter business knowledge source
```

这保证知识底座不会被临时材料或幻觉污染。

## 11. 长期治理

Evoloop 负责“何时写、何时归档、如何审核”的规则治理；GBrain 负责“存哪里、怎么检索、如何检测冲突”的知识基础设施能力。

两者的接口边界必须保持稳定，否则平台会重新退化成“内核和知识层耦合的一团逻辑”。
