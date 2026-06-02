# PM-Agent 产品与架构白皮书

> 本文档定义了 PM-Agent 平台的产品定位与技术架构。PM-Agent 是一个面向 B 端严肃场景（PM与运营）的通用任务与文档共创多角色协作平台。

---

## 1. 核心产品定位

在严肃的企业 B 端协作场景中，PM-Agent 作为一个智能调度与内容生产中枢，主要解决以下痛点：
1. **流程的确定性控制**：通过 `WorkflowEngine` 按照预定义的工作流规则执行，保障产出质量的稳定性。
2. **企业级安全治理**：利用 `ToolPolicy` 沙箱对 AI 能力调用（如读写文件、知识检索等）进行受控约束，避免敏感数据泄露或越权破坏系统。
3. **消除幻觉与业务分歧**：通过 `Arbitration`（用户裁决）机制，引入“人机混合（Human-in-the-loop）”模式，在关键业务取舍点将裁决权交还人类。

---

## 2. 系统架构设计 (The Multi-Role Collaboration Architecture)

PM-Agent 的系统架构分为前端工作台、API 接口层、通用任务引擎、服务与安全治理层四个核心层次：

```mermaid
graph TD
    User[业务用户 / PM / 运营] -->|创建并启动任务| API[FastAPI API Gateway]
    
    subgraph 引擎调度与控制面
    API -->|调度执行| Engine[WorkflowEngine]
    Engine -->|按步骤编排角色| Steps[多角色协作步骤]
    end
    
    subgraph 多角色协作矩阵 (当前工种)
    Steps -->|起草与主导| PM[PM 虚拟角色]
    Steps -->|可行性与风险评估| Tech[Tech 虚拟角色]
    Steps -->|边界与异常校验| QA[QA 虚拟角色]
    Steps -->|门禁控制| Reviewer[Reviewer 门禁角色]
    Steps -->|文档聚合编写| Writer[Writer 写作角色]
    end
    
    subgraph 底层安全与服务基座
    PM & Tech & QA & Reviewer & Writer -->|统一请求| ToolService[Tool Policy 受控执行区]
    ToolService -->|遇到决策阻碍| Arbiter[Arbitration 用户裁决系统]
    ToolService -->|获取外部知识| Knowledge[GBrain 知识检索适配]
    ToolService -->|读写工件与备份| Artifact[Artifact 存储与备份管理]
    end
    
    Arbiter -->|用户做出裁决| Engine
```

### 2.1 任务执行控制面 (Workflow Engine)
任务执行引擎负责管理任务的生命周期、状态流转、暂停恢复、重试与取消，并维护执行过程中的 Checkpoint。
- **配置化工作流**：任务由 `TaskDefinition` 进行静态定义（如 `manual` 操作手册和 `prd` 产品需求文档），引擎负责无状态地解释步骤。
- **并行执行支持**：引擎支持并行步骤执行，例如在评审阶段，`Tech` 与 `QA` 两个虚拟角色并发执行校验，提高协作效率。

### 2.2 虚拟协作角色设计 (Collaboration Roles)
在任务流内部，PM-Agent 抽象为 5 个具有不同职能特性的虚拟角色进行协同工作，均在共享的 `TaskContext` 下运行：
1. **PM 角色**：负责起草任务的初始提纲、核心需求或主线内容。
2. **Tech 角色**：负责校验技术可行性、指出实现风险与技术难点。
3. **QA 角色**：负责对流程边界、异常 Case 及可执行性进行挑剔性检查。
4. **Reviewer 角色**：作为严密的质检闸门，判断流程是否收敛，执行 Gate 检查。
5. **Writer 角色**：负责汇总之前所有角色的评审讨论历史，套用标准模板生成最终的 Markdown 文档。

### 2.3 安全与治理基座 (Governance Layer)
安全和稳定性是 PM-Agent 最底层的基因：
- **受控 Tool 调用**：角色运行期间不能直接读写文件、不直接访问网络，所有对资源的请求都必须由 `ToolService` 根据该任务的 `ToolPolicy` 白名单进行权限判断。权限不足时拒绝执行。
- **人机混合裁决 (Arbitration)**：在发生意见分歧（如 Tech 与 QA 在二审中存在重大分歧）或达到最大讨论轮次仍未收敛时，系统主动暂停，生成冲突包（Dispute Package）投递给用户，待用户反馈决策后从断点无缝恢复。
- **事件可溯源**：系统运行过程中的每一次 Tool 调用、角色发言和状态变更，都以结构化 Event 的形式沉淀到日志和事件总线中，保证协作全链路透明可审计。

---

## 3. 商业价值与竞争壁垒

1. **定制化的企业大脑**：
   通过 `Rule-Audit` 和 `diff` 规则提炼，用户在平台中对每一次决策和文档的修改，最终都能作为**私有法则**反馈给平台。随着系统使用，Agent 将深度掌握企业内部特有的系统架构与规范，成为最熟悉公司的内部专家。
2. **极高的企业级安全性与合规性**：
   相比直接使用具有系统根权限（Root）的通用开发 Agent，PM-Agent 的沙箱机制和受控白名单保证了业务人员可以在安全合规的前提下自主完成业务流程设计，绝不发生越权与敏感数据误删。
3. **清晰的责任审计链条**：
   在严肃的 B 端业务中，“可解释性”至关重要。PM-Agent 的结构化事件流为每一次文档生成和方案修改提供了无可篡改的链路记录，具备天然的合规友好属性。
