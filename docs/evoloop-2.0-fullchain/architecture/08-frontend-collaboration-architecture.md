# 08 前端协作架构

## 1. 前端不是日志终端

Evoloop 2.0 的前端不是“把后端打印出来”，而是让用户与平台共同完成任务的协作面板。

它需要承担三类职责：

1. 让用户理解系统现在在做什么。
2. 让用户能在关键节点介入和纠偏。
3. 让用户完成终稿和规则审核闭环。

## 2. 页面级架构

```text
Landing / Task Create
Workspace
Task Hall
Knowledge Base
Rule Audit
Workspace Onboarding
Recycle / Archive
```

### 2.1 Workspace

这是最核心页面，应该整合：

- 消息流
- DAG 可视化
- 当前节点状态
- 裁决请求卡片
- 文档编辑器
- interrupt / takeover 操作
- 终稿保存入口

## 3. Workflow Transparency

用户必须看到：

- 当前 DAG 是什么。
- 当前执行到哪个节点。
- 哪个 Agent 正在工作。
- 为什么请求裁决。
- 为什么系统降级。

因此前端应根据 SSE 渲染结构化状态，而不是解析文本日志。

## 4. 渐进式共创

### 4.1 旁听

用户默认可以旁听，但不强制立刻介入。

### 4.2 interrupt

用户可以暂停当前执行，要求系统在安全边界挂起。

### 4.3 takeover

用户可以修正某个错误事实或替代某个节点提供结论。

### 4.4 arbitration

当系统无法自动决策时，前端展示结构化 dispute package，让用户进行明确选择。

## 5. 文档编辑器的双态保存

前端必须明确区分：

| 动作 | 含义 |
|---|---|
| 草稿保存 | 只更新 Artifact 当前版本，不触发学习。 |
| 终稿保存 | 冻结交付版本，触发 Evidence + Diff Learning。 |

如果两个动作混成同一个按钮，后端很难分辨哪些改动是临时编辑，哪些才是可学习的最终结论。

## 6. 规则审核页

规则审核页不是简单列表，它应具备：

- CandidateRule 内容展示
- 证据摘要展示
- AI 草稿 vs 用户终稿差异摘要
- scope/protection/confidence 展示
- conflict/duplicate 提示
- approve / modify / reject 操作

前端在视觉上必须区分：

- `pending`
- `approved`
- `rejected`
- `store_failed`
- `conflict_check_degraded`

## 7. Workspace Onboarding

Workspace 初始化向导应显式要求用户选择：

- 领域包
- 额外扩展包
- 默认知识源
- 团队规则治理范围

这一步非常关键，因为它决定后续运行环境和专业 Agent 组合。

## 8. 事件消费模型

前端对事件的处理应分为：

### 8.1 Timeline Events

用于渲染消息流和运行时直播。

### 8.2 State Reconstruction Events

用于页面刷新后恢复：

- DAG 节点状态
- 当前等待原因
- 当前 artifact
- 是否已有 diff candidates

### 8.3 Toast / Hint Events

用于知识降级、GBrain 恢复、规则写入失败等轻量提示。

## 9. 刷新与回放

刷新页面后，前端不应丢失以下状态：

- 任务是否在等待用户裁决
- 当前 artifact 版本
- 当前 DAG 计划
- 已生成的 CandidateRule

因此前端需要：

1. 先从 API 获取任务当前状态。
2. 再回放历史事件。
3. 最后接上实时 SSE。

## 10. 与后端边界

前端不负责：

- 推断 DAG 合法性
- 解释 ToolPolicy
- 解析 prompt 或日志
- 直接调用 GBrain

前端只负责：

- 采集用户输入
- 展示结构化状态
- 发起显式控制动作
- 呈现清晰反馈
