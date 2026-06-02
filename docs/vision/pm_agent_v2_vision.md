# PM-Agent 2.0 产品构想与架构白皮书 (Vision 2.0)

> [!NOTE]
> 本文档定义了 PM-Agent 平台从 V1.0 走向 V2.0 的终极战略蓝图。我们的目标是打破单一固定流程的局限，打造一个**面向 B 端严肃场景（PM与运营）的通用多智能体协作平台（Multi-Agent Collaboration Platform）**。

---

## 1. 为什么需要 V2.0？(从 1.0 的痛点说起)

In V1.0 阶段，我们将重点放在了两个核心的高频痛点场景：`manual`（操作手册生成）和 `prd`（产品需求文档生成）。这一阶段验证了：
1. `WorkflowEngine` 对流程的确定性控制是极为有效的。
2. `ToolPolicy` 沙箱能保障企业安全性。
3. `Arbitration`（用户裁决）机制能有效解决 AI 幻觉和业务分歧。

**然而，V1.0 存在显著局限：**
- **场景固化**：每接入一个新的工作场景（如：竞品分析、运营活动策划、社群文案生成），都需要在后端硬编码一套全新的 `TaskDefinition` 和 `WorkflowSpec`。
- **能力孤岛**：不同角色（PM、Tech、QA、Reviewer）在代码层面耦合得过深，无法像“积木”一样被其他场景随意复用。
- **欠缺意图识别**：用户必须在界面上手动选择具体的入口，而不能简单地说一句“我要搞一场双十一的用户促活方案，帮我写个文档排个期”，然后期待系统自动运作。

---

## 2. V2.0 核心战略定位

**PM-Agent V2.0 的定位：泛 PM 与泛运营场景的统筹调度中枢。**

在 V2.0 中，平台不再是一个只能写 PRD 和手册的工具箱，而是一个**自带指挥系统与多个专业工种兵的联合司令部**。
核心逻辑从 `静态任务 -> 固定工作流 -> 输出` 进化为 `自然语言 -> 意图分析拆解 -> 动态组装 Subagents 协作 -> 输出`。

---

## 3. V2.0 全新架构设计图 (The Orchestrator-Workers Architecture)

V2.0 将采用业界最先进的多智能体协同模型，系统被解耦为三层：

```mermaid
graph TD
    User[业务用户 / PM / 运营] -->|泛化自然语言指令| Orchestrator[主调度大脑 Orchestrator Agent]
    
    subgraph 意图路由与调度层
    Orchestrator -->|1. 意图识别 & DAG 生成| Router[Task Router / Planner]
    end
    
    subgraph Subagents 插件矩阵 (专业兵种)
    Router -->|2. 按需动态分发| AgentA[研究员 Subagent \n 竞品/知识检索]
    Router -->|2. 按需动态分发| AgentB[推导者 Subagent \n PM逻辑推导/方案设计]
    Router -->|2. 按需动态分发| AgentC[审计员 Subagent \n Rule 抽取与合规校验]
    Router -->|2. 按需动态分发| AgentD[文案生成 Subagent \n 结构化文档/营销文案排版]
    end
    
    subgraph 底层安全与治理基座
    AgentA & AgentB & AgentC & AgentD -->|统一调用| ToolSandbox[Tool Policy 受控执行区]
    AgentA & AgentB & AgentC & AgentD -->|遇到决策阻碍| Arbiter[Arbitration 用户裁决系统]
    end
    
    Arbiter -->|恢复调度| Orchestrator
```

### 3.1 意图路由层 (Task Router / Orchestrator)
这是 V2.0 最核心的增量。主 Agent 不处理具体的文档编写，它只负责一件事：**理解并拆解任务**。
- **自动推导 Workflow**：用户输入“分析一下竞品的积分系统并输出一份改造建议”。Orchestrator 识别后，动态生成执行流：`研究员检索知识 -> 推导者撰写方案 -> 文案生成排版`。
- **全局视野**：监控各个 Subagent 的流转状态，当由于 Subagent 输出不达标时，决定是否循环重试（loopback）。

### 3.2 插件化智能体池与核心兵种设计 (Pluggable Subagents Registry)
V2.0 将把业务能力做极度的抽象化，每个 Subagent 必须实现标准化的接口（I/O契约）：
- **职责极窄（Single Responsibility）**：每一个 Subagent 只负责自己最擅长的一环，通过严格的 ToolPolicy 限制其越权行为。
- **即插即用**：动态挂靠，按需调用。

为了覆盖广阔的 PM 与运营场景，我们预先设计以下 **6 大核心 Subagent 兵种**作为 V2.0 平台的弹药库：

1. 🕵️ **竞品捕手 (Competitor Scout Subagent)**
   - **定位**：外部信息的嗅探雷达。
   - **专长**：专门负责在规划初期，从行业库或外网材料中提取特定功能（如积分体系、签到玩法）的业界标杆做法。
   - **输出**：不产出长篇大论，仅输出高度结构化的《竞品横评参数卡》和《功能亮点列表》。

2. 🧠 **逻辑推演者 (Logic Pathfinder Subagent)**
   - **定位**：PM 的左脑（严密的逻辑与边界推演）。
   - **专长**：接收到粗糙 of 业务目标后，立刻构建状态机，并在内部推演中进行“防守演练”。专门找出核心流程的缺失分支、极端异常 Case 和恶意作弊边界。
   - **输出**：业务流程图伪代码、需要用户裁决的《异常边界检查清单》。

3. 🏗️ **数据架构预检师 (Data Architect Subagent)**
   - **定位**：技术侧（Tech）前置顾问。
   - **专长**：在业务逻辑定稿前，预判该需求会对底层架构（如账户、订单流）带来什么冲击。评估“同步一致性”还是“异步最终一致性”，预测并发瓶颈。
   - **输出**：E-R 实体关联预判卡片，用于作为“技术成本”辅助用户在 `Arbitration`（裁决）时做出取舍。

4. ✍️ **营销包装师 (Marketing Copywriter Subagent)**
   - **定位**：运营的右脑（极强的情绪与受众感知）。
   - **专长**：当严谨的 PRD 或操作方案定稿后，负责将其转译为面向 To-C 用户的“活动大促推文”、“Push 话术剧本”或者面向 B 端客户的“Release Notes（发版说明）”。
   - **输出**：多渠道适配的带 Markdown 与 Emoji 格式的高转化文案。

5. ⚖️ **合规与风控审计员 (Compliance & Risk Auditor Subagent)**
   - **定位**：坚决的红线守门员（Reviewer / Gate）。
   - **专长**：只负责拦截和找茬。在任何文档输出为最终 Artifact 前，进行“违禁词扫描”、“超额承诺预警”、“黑灰产套利漏洞分析”以及企业内部历史 Rule 的强校验。
   - **输出**：打分报告。若低于阈值，强制截断并打回（触发 failed/blocked 状态要求重做）。

6. 🎨 **交互体验模拟器 (UX Simulator Subagent)**
   - **定位**：用户体验大使。
   - **专长**：站在小白用户的视角重跑“主链路”，计算页面/步骤的“漏斗转化流失风险”。
   - **输出**：体验阻力报告（如：“当前配置要求用户跨越 3 个页面完成退款，流失风险极高，建议改为当前页侧边弹窗”）。

### 3.3 坚不可摧的安全控制面 (Governance Layer)
V2.0 完整保留并增强了 1.0 的安全基因。
- 无论有多少个 Subagent 跑在上面，它们调用系统资源（读写库、拉资料、更新工件）必须通过 `ToolService`。
- 只要出现不可调和的逻辑冲突，必然由系统触发 `arbitration.requested` 事件抛给人类裁决，坚持**人机混合（Human-in-the-loop）**这一对抗幻觉的杀手锏。

---

## 4. 商业护城河：为什么是不可替代的？

1. **定制化的企业大脑，而非大厂标品**：
   虽然大厂的通用大模型也会提供多轮对话，但 V2.0 通过 `Rule-Audit` 和 `Subagent` 的分离，将每一次用户的裁决结果都作为**私有法则**反馈给了平台。系统运行半年后，平台内置的“产品推导 Subagent”将完全掌握该企业的私有系统架构与规范，成为最熟悉该公司的专家。
2. **场景可无限扩张（Infinite Use Cases）**：
   基于这种 Router-Worker 架构，商业上的想象力不再局限于 IT 研发团队。它可以被销售团队用来生成投标书，被运营团队用来追踪大促方案，底层复用的都是相同的 Workflow 状态机 and 裁决流。
3. **极高的容错与审计追溯能力**：
   在严肃的 B 端场景中，“可解释性”是最贵的特性。V2.0 中哪个 Subagent 做了什么决定，调了什么 Tool 遭遇了什么失败，都有不可篡改的事件（Event Stream）回传，满足最高级别的企业合规。

---

## 5. 从 V1.0 向 V2.0 的平滑演进路径

不需要推翻重来。我们当前的 V1.0 重构，正是通向 V2.0 的完美踏板：
* **当前第一步 (Phase 1 夯实底座)**：将 `manual` 和 `prd` 从旧版离散架构迁移到统一的 `TaskDefinition` 与 `WorkflowEngine` 下，跑通状态流、ToolService 和事件审计。
* **下一步 (Phase 2 标准化拆解)**：剥离 `WorkflowEngine` 中硬编码的 PM/Writer 分支逻辑，抽取为标准化、无状态的 `Subagent` 实现。
* **终局 (Phase 3 动态路由)**：在入口处挂载 Orchestrator，切断对固定模板的依赖，真正实现根据泛化指令自动装配工作流。
