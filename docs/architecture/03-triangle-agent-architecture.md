# 中台铁三角架构：任务沙盒、攻防与门禁

中台铁三角负责把用户的业务目标推进为可交付方案。它包含任务沙盒、PM/Tech/QA 三方攻防、Reviewer 质量门禁、人类仲裁接入和事件流输出。具体步骤编排和 Tool 调用边界见 [工作流与 Tool 架构](05-workflow-tool-architecture.md)。它只处理任务内推理与收敛，不负责长期知识沉淀，也不承载 Diff 经验提炼流程。

---

## 1. 定位

中台铁三角是一次任务的推理控制面。每次用户发起任务时，中台创建独立任务沙盒，向 GBrain 检索本次相关知识，然后驱动 PM、Tech、QA 在限定轮次内完成方案攻防。方案通过 Reviewer 门禁后，交给前台展示和终稿编辑。

它解决三个问题：

1. **避免单 Agent 自说自话**：PM 不能直接产出终稿，必须接受 Tech 和 QA 的反向压力。
2. **避免无限争论**：三方最多运行 3 轮，无法收敛时必须交给用户裁决。
3. **避免无门禁交付**：铁三角达成共识后，还必须通过 Reviewer 的独立质量门禁。

## 2. 核心组件

| 组件 | 职责 | 输入 | 输出 |
|---|---|---|---|
| Task Sandbox | 管理单次任务的上下文、轮次、状态和事件流 | 用户目标、材料、知识检索结果 | 任务状态、事件、最终方案草稿 |
| Workflow Engine | 按 TaskDefinition 推进 PM、Tech、QA、Reviewer、Writer 步骤 | WorkflowSpec、TaskContext、StepResult | 步骤状态、checkpoint、暂停恢复结果 |
| Tool Service | 为 Agent 提供受控材料、知识、产物、Diff 能力 | ToolSpec、ToolPolicy、ToolCall | ToolResult、审计事件、关联产物 |
| PM Agent | 形成主方案，吸收 Tech/QA/用户反馈并修订 | 用户目标、知识上下文、反驳意见 | 方案草案、修订说明、待裁决问题 |
| Tech Lead Agent | 从架构可行性角度挑战方案 | PM 草案、架构原则、平台事实 | 技术风险、替代方案、阻塞项 |
| QA Agent | 从异常流和边界条件角度挑战方案 | PM 草案、Tech 风险、业务规则 | 异常用例、验收阻塞、补偿要求 |
| Reviewer Agent | 在输出前执行独立质量门禁 | 收敛方案、用户裁决、审查标准 | 通过、驳回、纠偏建议 |
| Arbitration Adapter | 将死锁分歧打包给前台，并接收用户裁决 | 分歧点、三方立场、风险说明 | 用户裁决、最高优先级约束 |
| Event Streamer | 将任务进展实时推送到前台 | 任务状态、Agent 发言、门禁结果 | 可订阅事件流 |

## 3. 任务生命周期

```text
CREATED
  -> CONTEXT_LOADING
  -> ROUND_RUNNING
  -> ROUND_REVIEWING
  -> NEEDS_ARBITRATION
  -> ARBITRATION_APPLIED
  -> GATE_REVIEWING
  -> READY_FOR_USER_EDIT
  -> CLOSED
```

| 状态 | 说明 | 退出条件 |
|---|---|---|
| CREATED | 任务已创建，尚未装载上下文 | 用户输入完成校验 |
| CONTEXT_LOADING | 从 GBrain 检索平台事实、业务规则、架构原则和可信法则 | 上下文包生成完成，或进入降级模式 |
| ROUND_RUNNING | PM、Tech、QA 按顺序进行本轮攻防 | 本轮三方输出完成 |
| ROUND_REVIEWING | 中台判断本轮是否收敛 | 收敛、继续下一轮、或触发仲裁 |
| NEEDS_ARBITRATION | 三方争议无法自动收敛，等待用户裁决 | 前台提交用户裁决 |
| ARBITRATION_APPLIED | 用户裁决被写入任务上下文 | PM 根据裁决重写方案 |
| GATE_REVIEWING | Reviewer 对收敛方案执行门禁 | 通过或驳回 |
| READY_FOR_USER_EDIT | 草案可交给前台编辑保存 | 用户确认进入终稿编辑 |
| CLOSED | 任务运行态结束 | 上下文归档，运行实例销毁 |

## 4. 上下文包

任务沙盒启动时，中台生成统一上下文包，供 PM、Tech、QA、Reviewer 使用。

```text
TaskContext
  task_goal            用户目标
  user_constraints     用户补充约束和偏好
  source_materials     用户提交的材料摘要
  knowledge_context    GBrain 检索到的事实、规则、原则和可信法则
  round_history        已完成轮次记录
  open_disputes        尚未解决的争议点
  user_decisions       用户打断和仲裁结果
  gate_requirements    Reviewer 门禁要求
  degradation_state    是否使用知识快照降级运行
```

上下文包有三个约束：

1. **所有 Agent 共享同一事实基线**：PM、Tech、QA 不能各自私下检索并形成冲突事实。
2. **用户裁决优先级最高**：一旦用户裁决写入 `user_decisions`，后续 Agent 只能在该约束下继续推演。
3. **轮次历史上下文绑定（Round History Context Binding）**：大模型调用层（`LLMPort`）会把 `round_history` 中所有历史发言按 `【Role】: 内容` 的格式整合进推理 `messages` 中，保证所有 Agent 在发言时具备前文上下文的完整认知，避免孤立发言。

## 5. 三方角色细化

### 5.1 PM Agent

PM 是方案主笔，不是最终裁决者。它负责把用户目标转化为可讨论的主方案，并在每轮吸收 Tech、QA 和用户反馈。

PM 必须输出：

- 业务目标拆解。
- 主流程方案。
- 涉及的服务、数据和外部依赖。
- 已采纳的 Tech/QA 反馈。
- 尚待裁决的问题。

PM 不允许：

- 忽略 Tech 或 QA 的阻塞意见直接定稿。
- 把未确认的技术假设写成已确定事实。
- 在用户已有裁决后重新提出相反方向。

### 5.2 Tech Lead Agent

Tech 负责从系统可行性角度挑战 PM 方案。它不追求“更复杂”，而是确保方案在架构边界、数据一致性、容量和依赖链路上站得住。

Tech 必须检查：

- 服务边界是否清晰。
- 同步/异步链路是否合理。
- 数据一致性要求是否明确。
- 关键依赖是否有降级策略。
- 高并发、容量、超时和重试是否有设计。
- 是否存在单点、环形依赖或过度耦合。

Tech 输出分三类：

| 类型 | 含义 | 后续处理 |
|---|---|---|
| Blocking | 不解决就不能继续 | PM 必须修订或请求用户裁决 |
| Risk | 可接受但必须暴露 | 写入风险与缓解策略 |
| Suggestion | 优化建议 | PM 可采纳或说明不采纳原因 |

### 5.3 QA Agent

QA 负责模拟最坏情况，确保方案不是只覆盖正常流程。它关注异常流、脏数据、用户误操作、第三方失败和补偿机制。

QA 必须检查：

- 用户输入缺失、重复、非法或过期时如何处理。
- 上游/下游服务超时、失败、返回脏数据时如何处理。
- 重试是否会造成重复写入或重复扣减。
- 并发请求是否会造成状态错乱。
- 降级后用户看到什么、系统保留什么证据。
- 失败后是否有补偿、对账、回滚或人工介入路径。

QA 输出至少包含：

- 致命异常用例。
- 必须补齐的前置条件。
- 必须展示给用户的错误状态。
- 必须记录的审计或排查信息。
- 验收时需要覆盖的测试场景。

### 5.4 Writer Agent

Writer Agent 是最终产物的整合编写者。在攻防流程收敛并通过门禁后，它负责提取 PM 的草案、Tech 的技术反馈、QA 的异常用例以及人类用户的历次裁决，融会贯通，整合编写出结构清晰、格式标准且完全真实的最终规范文档。

**动态产物渲染机制（Dynamic Artifact Rendering）**：
- **AI 真实生成优先**：当大模型作为 Writer 角色输出了包含符合技术规范（如含有 PRD 核心背景及业务目标特征头部）的真实排版文件时，系统将直接采用 AI 真实生成的内容作为产物写入 Markdown。
- **自动化测试 Fallback**：若处于自动化测试环境（使用 `FakeLLM` 输出占位简短文字）或生成内容不满足结构特征，则系统自动降级回退至预置的静态结构化模板，以在确保不破坏单元测试结构与断言的同时，保证了业务的鲁棒性。

## 6. 轮次协议

每一轮都按固定协议运行，避免自由聊天失控。

```text
Round N
  1. PM 输出方案版本 Vn
  2. Tech 输出技术挑战清单
  3. PM 输出技术修订 Vn.1
  4. QA 输出异常挑战清单
  5. PM 输出综合修订 Vn.2
  6. 中台判断是否收敛
```

中台判断收敛时检查：

- 是否仍有 Blocking 技术问题。
- 是否仍有致命异常用例未处理。
- PM 是否说明每条反对意见的处理结果。
- 方案是否违反用户裁决。
- 是否达到最大轮次。

最大轮次为 3。达到 3 轮仍有阻塞项时，不能继续自动推演，必须生成分歧包交给用户。

## 7. 分歧包设计

分歧包是中台和前台之间的人类仲裁协议。它必须把争议压缩成用户能拍板的选项，而不是把完整聊天记录丢给用户。

```text
DisputePackage
  title                 争议标题
  background            争议背景
  decision_needed       用户需要拍板的问题
  options[]             可选方案
    label               方案名称
    pm_position         PM 观点
    tech_position       Tech 观点
    qa_position         QA 观点
    benefit             收益
    cost                代价
    risk                风险
    recommended         是否推荐
  impact_after_decision 裁决后影响哪些方案部分
```

分歧包要求：

1. 每个选项都必须说明收益、代价和风险。
2. 推荐项必须给出理由，但不能替用户直接决定。
3. 选项不能超过 3 个，避免把仲裁变成二次需求分析。
4. 用户裁决必须原样记录，并进入后续任务上下文。

## 8. Reviewer 门禁

Reviewer 是后置质量门禁，不参与前期自由创作。它检查“方案是否可交付”，而不是继续提出无限扩展想法。

Reviewer 检查项：

| Gate | 检查内容 | 不通过示例 |
|---|---|---|
| G1 目标一致性 | 是否符合用户目标和用户裁决 | 用户裁决同步链路，方案仍写异步优先 |
| G2 架构完整性 | 服务边界、依赖、数据流是否清晰 | 只写功能，不写依赖服务和数据流 |
| G3 异常完整性 | 异常流、降级、补偿是否覆盖关键失败 | 只写成功路径，没有超时和重试策略 |
| G4 风险透明度 | 风险是否被明确暴露并给出缓解策略 | 把高一致性风险隐藏在一句“后续优化”里 |
| G5 可交付性 | 输出是否能被研发、测试、业务共同理解 | 只有抽象口号，没有可执行约束 |

Reviewer 输出三种结果：

- **PASS**：可以交给前台进入终稿编辑。
- **REVISE**：必须按纠偏意见回到 PM 修订。
- **ARBITRATE**：发现新业务取舍，必须交给用户裁决。

## 9. 事件流输出

中台必须把关键过程实时推送给前台，避免用户只能看到最终结论。

| 事件 | 触发时机 | 负载 |
|---|---|---|
| task.created | 任务创建 | 任务 ID、目标摘要 |
| context.loaded | 上下文加载完成 | 知识来源、是否降级 |
| round.started | 新轮次开始 | 轮次号 |
| agent.message | Agent 输出 | 角色、内容、轮次 |
| dispute.detected | 发现死锁争议 | 分歧包摘要 |
| arbitration.required | 需要用户裁决 | 完整分歧包 |
| arbitration.applied | 用户裁决已应用 | 裁决内容 |
| gate.started | Reviewer 门禁开始 | 草案版本 |
| gate.completed | Reviewer 门禁完成 | PASS/REVISE/ARBITRATE |
| task.ready | 草案可编辑 | 草案 ID |
| task.closed | 任务关闭 | 结束原因 |

## 10. 异常处理

### 10.1 知识检索失败

如果 GBrain 不可用，中台进入降级模式：

1. 使用最近一次可信知识快照。
2. 在事件流中发送 `context.loaded`，标记 `degraded=true`。
3. 要求 Agent 不把不确定事实写成确定结论。
4. 在 Reviewer 门禁中增加“降级知识风险”检查。

### 10.2 单个 Agent 失败

如果某个 Agent 调用失败：

1. 重试一次。
2. 仍失败则把失败角色、阶段和影响写入事件流。
3. 如果失败角色是 PM，任务不能继续。
4. 如果失败角色是 Tech 或 QA，可以请求用户选择：降级继续或终止任务。
5. 如果失败角色是 Reviewer，不能交付，必须重试或终止。

### 10.3 用户长时间不仲裁

如果任务进入 `NEEDS_ARBITRATION` 后用户未响应：

1. 保持任务挂起，不自动代替用户决策。
2. 前台展示待裁决状态。
3. 中台保留上下文，等待用户恢复。
4. 超过保留期限后关闭任务，但不把未裁决方案标记为完成。

## 11. 与其他架构边界的关系

- 与 [前台架构](01-frontend-architecture.md)：中台输出事件流、分歧包、门禁结果和草案；前台返回用户打断和仲裁。
- 与 [知识库架构](02-knowledge-base-architecture.md)：中台只向 GBrain 检索知识，不直接写入知识。
- 与 [Diff 流程架构](04-diff-workflow-architecture.md)：中台在任务结束后移交草稿、终稿、审查记录和仲裁记录作为证据；Diff 流程独立负责经验提炼。
- 与 [工作流与 Tool 架构](05-workflow-tool-architecture.md)：中台角色只在 Workflow 步骤内运行，并只能使用 ToolPolicy 白名单中的受控工具。
