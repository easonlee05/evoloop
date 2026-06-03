# PM-Agent 产品与架构白皮书

> 状态说明：本文档保留为 2.0 阶段历史白皮书，不再作为当前目标架构真相源。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。
> 若本文与 3.0 文档冲突，以 3.0 文档为准。

> 本文档定义了 PM-Agent 平台从 1.0 迈向 2.0 的产品定位与技术架构。2.0 阶段的核心演进是从“静态工作流”跨越到以**主控 Agent 为中枢的动态意图路由**体系，并引入了**可插拔的领域特化 (Pluggable Domain Specialization)** 机制。

---

## 1. 核心产品定位

在严肃的企业 B 端协作场景中，PM-Agent 作为一个智能调度中枢，解决以下痛点：
1. **意图的精准拆解与分发**：将复杂业务需求拆解为可由垂类专家执行的子任务有向无环图 (DAG)。
2. **基于插件的领域特化 (Plugin-based Domain Specialization)**：提供一个绝对通用的基础工作流底座，通过加载不同行业的“扩展包 (Expansion Packs)”实现极高深度的特化（例如云原生领域的 SRE 左移理念），在保证深度的同时绝不损失商业通用性。
3. **企业级安全与渐进式共创**：利用沙箱进行权限隔离，允许用户随时打断并接管流程。

---

## 2. 系统架构设计 (The Dynamic Agentic Topology)

PM-Agent 2.0 废弃了硬编码的静态流水线，演进为**主控 Agent + 动态注册的 Subagent 插件池**的星型网络拓扑：

```mermaid
graph TD
    User[业务用户 / PM / 运营] -->|多模态输入/文本| API[FastAPI API Gateway]
    
    subgraph 引擎调度与通用控制面 (Orchestrator)
    API -->|调度执行| MainAgent[主控 Orchestrator Agent]
    MainAgent -->|反射可用插件 & 生成 DAG| DAG[Task Graph 任务流]
    end
    
    subgraph 动态 Agent 注册表 (Dynamic Registry Hub)
    DAG --> Base[基础专家包: 交互专家/文案代理]
    DAG -->|装载云原生扩展包| CloudNative[云原生包: SRE/可观测性/GitOps管家]
    DAG -->|可替换装载| OtherPack[电商/Web3/游戏等扩展包...]
    end
    
    subgraph 底层工程与通信基座
    Base & CloudNative -->|标准信封协议交互| EventBus[Event Bus 分布式事件总线]
    EventBus -->|同步回| MainAgent
    MainAgent -->|状态读写| Blackboard[(领域共识黑板)]
    MainAgent -->|提取 IaC 与业务法则| RuleService[Rule Lifecycle 规则引擎]
    end
    
    EventBus -->|渲染透视窗| UI[渐进式共创前端 UI]
    UI -->|用户随时 Takeover| MainAgent
```

### 2.1 主控 Agent (Main Orchestrator)
负责拆解 Prompt 生成无环依赖任务流。主控具备**反射能力 (Capability Reflection)**，在初始化时自动读取当前租户安装了哪些 Subagent 扩展包，据此决定能将任务路由给谁。

### 2.2 行业扩展包模式 (Domain Expansion Packs)
系统底层不再“写死”任何特定的专家，而是以插件包形式分发能力。
- **基础包 (Core Pack)**：内置交互体验专家、内容文案代理。
- **特化扩展包示例（云原生 Cloud-Native Pack）**：当系统切入 IaaS/PaaS 赛道时，加载该包，即刻点亮微服务边界分析师、SRE容灾门卫、可观测性架构师与 GitOps 编排管家等顶级特化专家。

### 2.3 渐进式前端 (Progressive UX)
前端实时渲染总线调度日志，用户可随时接管微调。

---

## 3. 架构演进与工程化盲区预警 (Engineering Challenges)

1. **上下文碎片化**：通过 **共享黑板 (Blackboard)** 同步领域共识（如微服务拓扑），防止代理瞎子摸象。
2. **通信死锁**：信封协议内置 **TTL** 熔断机制。
3. **细粒度权限失控**：执行严格的 **RBAC** 工具沙箱拦截。
4. **并发时序依赖**：强制上游定稿后，才唤醒下游。

---

## 4. 商业壁垒：通用底座与无限特化生态

1. **极致的架构通用性与扩展性**：底座与行业逻辑完全解耦，未来无论是进军 SaaS、Web3 还是出海赛道，只需开发注册相应的 Domain Pack。
2. **深度的私有法则账本**：法则库融合了自然语言规范与声明式基础设施 (OPA/Gatekeeper) 检测，成为企业的核心数字资产。
