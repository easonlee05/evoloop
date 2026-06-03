# 10 安全与治理架构

## 1. 总体原则

Evoloop 2.0 的安全与治理不是附加功能，而是平台内核的一部分。因为：

- Agent 默认会放大越权风险。
- 规则学习一旦错误入库，会污染未来任务。
- 多租户 Workspace 需要明确边界。

## 2. 最小权限原则

Agent 不拥有默认外部能力。任何外部动作都必须满足：

```text
Tool exists
  + ToolPolicy allows role/node/workspace
  + arguments validate
  + call is audited
```

### 2.1 Denied 与 Failed

`denied` 表示策略拒绝；`failed` 表示尝试执行但失败。两者必须在模型、事件、前端和审计中严格区分。

## 3. 多租户隔离

Workspace 是租户边界，因此必须在以下对象上强制携带 `workspace_id`：

- Task
- Artifact
- Material
- FrozenEvidence
- CandidateRule
- Rule review records

跨 Workspace 的直接资源读取必须被拒绝，即使资源 id 可猜到也不应成功。

## 4. 敏感信息最小暴露

### 4.1 不应进入事件/日志的数据

- API key / token / secret
- 完整 authorization header
- 服务器绝对路径
- 原始 prompt
- 未授权材料全文

### 4.2 可进入事件的数据

- 安全摘要
- 引用 id
- 状态枚举
- 用户可理解的错误码

## 5. 规则治理

规则会反向影响未来任务，因此 CandidateRule 需要平台级治理。

### 5.1 入库前治理

- 检查 scope 是否超权
- 检查 protection level 是否合理
- 检查与 `rules-global` 是否冲突
- 检查 evidence 是否完整

### 5.2 入库后治理

- hit tracking
- stale detection
- archive decision
- 审核人和证据可追溯

## 6. Pack 治理

第三方或团队自定义包进入系统前必须经过：

- manifest 校验
- SlotContract 兼容性校验
- ToolPolicy 范围校验
- 可信等级声明

不允许“带着任意 shell/network 能力”的 Agent 直接注册到平台运行时。

## 7. 用户接管的安全语义

Takeover 允许用户覆盖事实，但不应：

- 伪造历史事件
- 篡改旧 evidence
- 无痕覆盖旧候选规则

Takeover 应被记录为独立事件和结构化记录，保留前后差异。

## 8. 审计架构

平台应至少可审计：

- 谁创建了任务
- 哪些 Agent 被加载
- 谁发起了 takeover
- 哪些 Tool 被 denied/failed
- 哪个用户批准了哪条规则
- 哪条规则写入了哪个 GBrain source

## 9. 失败隔离

### 9.1 Tool 层失败

不应导致整个平台崩溃，只影响当前节点或当前子链路。

### 9.2 Diff / Rule 写入失败

不应回滚主任务交付状态，只影响学习链路状态。

### 9.3 Pack 加载失败

不应污染其他 Workspace 的运行环境。

## 10. 安全与产品体验的平衡

安全机制不应只表现为“后端拒绝”，前端应能解释：

- 为什么被拒绝
- 是权限问题、策略问题还是系统故障
- 用户下一步应该做什么

这样治理才不会退化成“看不懂的失败”。
