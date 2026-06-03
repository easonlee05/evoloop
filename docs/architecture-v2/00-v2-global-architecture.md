# 00 EvoLoop 2.0 全局架构设计 (Global Architecture)

> 状态说明：本文档保留为早期 2.0/v2 架构草稿，不再是当前目标架构真相源。
> 当前应优先阅读 `docs/evoloop-3.0/architecture/00-global-architecture.md` 和 `docs/evoloop-3.0/technical/00-evolution-roadmap.md`。
> 若本文与 3.0 文档冲突，以 3.0 文档为准。

## 1. 架构演进背景

PM-Agent 1.0 采用固定的流水线模式，难以应对现代架构下的复杂协同需求。2.0 版本引入了 **动态意图路由拓扑 (Dynamic Agentic Topology)**。更重要的是，为了兼顾特定行业的“极致深度”（如云原生的硬核要求）与推向市场的“极致广度”，2.0 底座采用了 **可插拔的领域驱动框架 (Pluggable Domain-Driven Framework)**。

## 2. 核心架构组件

### 2.1 主控 Agent (Main Orchestrator)
作为大脑，负责：
- **反射可用能力 (Capability Reflection)**：启动时读取 `Agent Registry Hub`，感知当前系统安装了哪些专家插件。
- **深层意图拆解与动态 DAG 生成**：根据感知到的可用专家池，将目标分解并构建有向无环图。如果系统安装了“安全包”，主控就会把安全审计任务挂入 DAG。
- **聚合与仲裁**：组装方案，确保上下游契约对齐。

### 2.2 动态 Agent 注册表 (Dynamic Agent Registry)

系统底座**不硬编码**任何特定的专家，也不限制 Agent 的总数。所有的 Subagent 都通过标准接口注册为插件。能力通过 **扩展包 (Expansion Packs)** 分发，并采用 **”抽象插槽覆盖 (Override) + 动态追加 (Append)”** 机制：

*   **基础抽象插槽 (Core Slots)**：系统内核定义的最基本协同角色（如 `UX_Critic` 交互批评家、`Copywriter` 文案代理、`Biz_Analyst` 业务分析师、`Deploy_Gen` 部署生成器），基础包 (Core Pack) 为其提供 Fallback 默认实现。
*   **插槽覆盖 (Override)**：扩展包可以指定并**覆盖替换**已有的基础插槽（例如，用 `云原生微服务分析师` 替换 `通用业务分析师`）。
*   **动态追加 (Append)**：扩展包可以根据行业特有需求，**任意追加注册**全新的专家插槽（例如，云原生特有的 `Reliability_Guard` SRE 门卫，这在基础包中是不存在的）。

因此，不同扩展包加载后，Workspace 内生效的 Agent 数量和职能是**完全动态且不固定**的。

#### 2.2.1 SlotContract — 插槽接口契约（版本化）

每个插槽定义一份强类型的 `SlotContract`，声明该槽位的输入输出 schema。任何 OVERRIDE 的 Agent 在注册时必须通过 Registry 的静态兼容性校验，否则拒绝加载。

```python
from pydantic import BaseModel
from typing import List

class SlotContract(BaseModel):
    “””插槽接口契约 — 定义该槽位的输入输出 schema 版本。”””
    slot_name: str
    version: str                           # 语义化版本号 (如 “1.0”, “2.0”)
    required_context_keys: List[str]       # 输入 context_slice 中必须包含的 key
    optional_context_keys: List[str] = []  # 可选的 key
    output_schema: str                     # 输出 JSON Schema 标识

# 基础包定义的契约
BIZ_ANALYST_CONTRACT = SlotContract(
    slot_name=”Biz_Analyst”,
    version=”1.0”,
    required_context_keys=[“business_requirements”],
    optional_context_keys=[“user_stories”],
    output_schema=”BizAnalysisResult_v1”
)

# 云原生包覆盖时，必须声明实现了哪个版本的契约
# 如果需要新的 context_keys（如 service_topology），则必须升级契约版本
BIZ_ANALYST_CONTRACT_V2 = SlotContract(
    slot_name=”Biz_Analyst”,
    version=”2.0”,
    required_context_keys=[“business_requirements”, “service_topology”],
    optional_context_keys=[“api_contracts”],
    output_schema=”BizAnalysisResult_v2”
)
```

Registry 加载规则：
- OVERRIDE Agent 声明的 `contract_version` 必须与当前系统中该 Slot 的 Contract 版本兼容。
- 若 OVERRIDE Agent 需要新增输入字段，必须发布新版本 Contract，主控的 Context Slice 生成逻辑同步适配。
- 不兼容时 Registry 拒绝加载并输出明确的错误信息（而非运行时崩溃）。

#### 2.2.2 基础包 (Core Pack) - 默认 Fallback
提供 4 个最底线的通用插槽，确保即使没有任何特化包，系统也能跑通基本的产品工作流：
- **通用交互体验专家 (UX_Critic)**：处理断网、空数据及多模态视觉校验。
- **通用内容文案代理 (Copywriter)**：文本与公关口径把控。
- **通用业务分析师 (Biz_Analyst)**：常规业务逻辑完备性与流程拆解。
- **通用部署生成器 (Deploy_Gen)**：生成常规交付物大纲与部署步骤。

#### 2.2.3 官方预置特化包：云原生 (Cloud-Native Pack)
当 Workspace 挂载此包时，通过”覆盖”与”追加”动态重构专家网络：
- **微服务边界分析师 (Biz_Analyst Override - 覆盖)**：专门识别微服务拆分边界，评估 API/gRPC 契约兼容性。声明实现 `Biz_Analyst` Contract v2.0。
- **交付与 GitOps 编排管家 (Deploy_Gen Override - 覆盖)**：剥离系统依赖转换为 Task，输出 K8s CRD/YAML 配置草案。
- **SRE 与高可用容灾门卫 (Reliability_Guard Append - 新增追加)**：评估限流与熔断策略，审查 Pod 资源开销 (CPU/Mem limits) 和跨可用区容灾。
- **可观测性与埋点架构师 (Observability_Architect Append - 新增追加)**：输出业务埋点，以及 Prometheus 监控面板与 OpenTelemetry 链路告警策略。
- **活动运营与策略引擎 (Campaign_Ops Append - 可选追加)**：处理复杂的人群定向、限额互斥（视具体业务线加载）。

**💡 运行期效果**：装载云原生包后，主控可调度的专家库动态融合为 **7 个 Agent**（2 个通用 Fallback 保留 + 2 个云原生覆盖 + 3 个云原生追加）。

---

## 3. 动态路由拓扑与流转机制

### 3.1 DAG 生成策略：模板骨架 + LLM 动态填充

为了在确定性与灵活性之间取得平衡，DAG 的生成采用**分层策略**：

**第一层：任务类型模板（人定义，数量有限，确定性 100%）**

每种任务类型预定义一个 DAG 骨架模板（参与哪些 Slot、基本依赖顺序），由开发者以配置文件形式维护：

```yaml
# task_templates/cloud_native_promotion.yaml
template_name: "大促活动方案"
required_slots: ["Biz_Analyst", "Reliability_Guard", "Observability_Architect", "Copywriter"]
dag_edges:
  - from: "Biz_Analyst"
    to: ["Reliability_Guard", "Observability_Architect"]  # 可并行
  - from: ["Reliability_Guard", "Observability_Architect"]
    to: "Copywriter"  # 等待上游全部完成
```

**第二层：LLM 动态填充（为每个节点生成 context_slice 和 task_objective）**

主控根据用户输入，调用 LLM 为模板中的每个节点填充具体的执行指令——LLM 只决定"怎么做"，不决定"谁来做、什么顺序做"。

**第三层：全新场景的 Fallback（LLM 生成 DAG + 校验 + 用户确认）**

当用户输入不匹配任何已有模板时：
1. LLM 生成完整的 DAG 结构
2. 经过 DAGValidator 校验（见 §3.2）
3. 推送给前端，用户确认后才执行
4. 用户确认的 DAG 可选择沉淀为新模板，下次直接使用

### 3.2 DAG 校验层 (DAGValidator)

无论 DAG 来源是模板还是 LLM 生成，在执行前必须经过校验：

```python
class DAGValidator:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
    
    def validate(self, dag: TaskDAG) -> ValidationResult:
        errors = []
        
        # 1. 结构合法性：拓扑排序检测环
        if self._has_cycle(dag):
            errors.append(CycleDetectedError(dag.edges))
        
        # 2. 节点存在性：所有目标 Slot 必须在当前 Registry 中已注册
        for node in dag.nodes:
            if node.agent_slot not in self.registry.active_slots:
                errors.append(UnknownSlotError(node.agent_slot))
        
        # 3. 契约兼容性：每个节点的 context_slice 是否满足对应 SlotContract
        for node in dag.nodes:
            contract = self.registry.get_contract(node.agent_slot)
            missing_keys = set(contract.required_context_keys) - set(node.context_slice_keys)
            if missing_keys:
                errors.append(ContractMismatchError(node, missing_keys))
        
        # 4. 连通性：所有节点可从起点到达（无孤岛）
        if self._has_orphans(dag):
            errors.append(OrphanNodeError(...))
        
        return ValidationResult(errors=errors, is_valid=len(errors) == 0)
```

校验失败时：
- 来自模板的 DAG 校验失败 → 属于系统 bug，直接抛异常给开发者
- 来自 LLM 的 DAG 校验失败 → 自动重试一次（带校验错误信息作为 LLM 上下文），再次失败则上报用户

### 3.3 Plan-then-Execute 模式

无论 DAG 来源，执行前均经过 Plan 确认环节：

1. **DAG 草案生成**（模板实例化或 LLM 输出）
2. **DAGValidator 校验通过**
3. **SSE 推送前端**："主控建议如下执行方案 [DAG 可视化]"
4. **用户确认**（或修改/删除不需要的节点）
5. **引擎开始执行**

对于来自模板的"常规任务"，可配置为自动确认（auto_approve=true），跳过等待用户步骤。

### 3.4 运行时路由流转

1. **上下文切片**：主控根据 SlotContract 中声明的 `required_context_keys`，从 Blackboard 中精确提取对应字段下发给目标代理。
2. **沙箱并行**：代理基于标准的信封协议并行执行。即使是第三方开发的 Agent 插件，也受到引擎底层 RBAC 工具沙箱的严格权限控制。
3. **回退与前端共创**：一旦出现冲突（Blackboard Merge 返回 CONFLICT_ESCALATE），立即挂起并向前端 Event Bus 推送，请求人类用户接管。

---

## 4. 文档索引与实现路线

### 4.1 v2 架构文档全集

| 编号 | 文档 | 核心内容 | 状态 |
|---|---|---|---|
| 00 | 本文 | 全局架构、DAG 策略、SlotContract、DAGValidator | 设计完成 |
| 01 | [通信协议](01-agent-communication-protocol.md) | MessageEnvelope、双层熔断（Session Budget）、Bus 职责 | 设计完成 |
| 02 | [状态与上下文](02-context-and-state-management.md) | Blackboard、MergePolicy、乐观锁、asyncio.Lock | 设计完成 |
| 03 | [规则生命周期](03-rule-lifecycle-architecture.md) | 规则分级（CRITICAL/STANDARD/DEPRECATED）、淘汰与保护 | 设计完成 |
| 04 | [体验与向导](04-progressive-ux-and-multimodal.md) | Takeover Checkpoint、脏节点传播、Plan-then-Execute UX | 设计完成 |
| 05 | [工程框架与部署](05-development-framework-and-deployment.md) | 目录结构、BaseSubagent、内存总线、JSON 可序列化约束 | 设计完成 |
| 06 | [GBrain 集成](06-gbrain-integration-architecture.md) | MCP 接入、Tool 封装、知识检索、法则入库、降级策略 | 设计完成 |

### 4.2 实现优先级（推荐顺序）

```text
Phase 1: 核心引擎骨架（不依赖 LLM 即可跑通）
  1. app/core/envelope.py          → MessageEnvelope + SessionBudget (01)
  2. app/core/blackboard.py        → BlackboardState + MergePolicy + asyncio.Lock (02)
  3. app/core/registry.py          → SlotContract + Registry 加载 + 静态校验 (00 §2.2.1)
  4. app/agents/base.py            → BaseSubagent 抽象基类 (05)
  5. app/core/event_bus.py         → asyncio.Queue + SessionBudgetTracker (01 §4)
  6. app/core/dag.py               → TaskDAG 数据结构 + DAGValidator (00 §3.2)

Phase 2: 主控逻辑
  7. app/core/orchestrator.py      → 模板加载 + LLM 填充 + Plan-then-Execute (00 §3.1, §3.3)
  8. app/core/context_slicer.py    → 根据 SlotContract 裁切 context_slice (00 §3.4)
  9. app/core/merge_engine.py      → 按 MergePolicy 执行 Merge + 版本校验 (02 §3.3)

Phase 3: GBrain 接入
  10. app/tools/gbrain_mcp_client.py → MCP Client 连接管理 (06 §2.2)
  11. app/tools/knowledge_tool.py    → query/search/put_page 封装 (06 §2.3)

Phase 4: 扩展包与 Agent 实现
  12. app/agents/core_pack/          → 4 个基础 Agent (05 §2.1)
  13. app/agents/cloud_native/       → 云原生扩展包 (05 §2.1)
  14. task_templates/                 → YAML DAG 模板 (00 §3.1)

Phase 5: 前端交互
  15. app/api/server.py             → FastAPI + SSE (Plan-then-Execute 推送)
  16. Takeover + Checkpoint 机制    → SUSPEND/RESUME 信号 (04 §3.2)

Phase 6: 规则生命周期
  17. app/services/rule_service.py  → CRITICAL/STANDARD 分级 + 淘汰逻辑 (03)
```

### 4.3 AI 编程工具执行指南

给 Codex / Antigravity / Claude Code 的关键指引：

1. **每个文件只做一件事**：一个 Agent 一个文件，一个 Tool 一个文件，一个 MergePolicy 一个文件。不要把多个概念塞进一个文件。
2. **先跑通 Phase 1 再写 Agent**：Phase 1 的 6 个文件是纯数据结构和校验逻辑，不依赖 LLM，可以 100% 单元测试覆盖。
3. **SlotContract 是硬约束**：任何 Agent 实现必须先声明 `slot_name`、`action_type`、`contract_version`，Registry 加载时自动校验。测试时先 `assert registry.load(agent_class)` 不抛异常。
4. **Blackboard 的 asyncio.Lock 不可省略**：即使看起来"只有一个协程在写"，也必须用 Lock。asyncio 的 await 点会让出控制权。
5. **DAG 模板是 YAML 配置文件，不是 Python 代码**：模板放在 `task_templates/` 目录，主控读取并实例化。新增任务类型只需加一个 YAML 文件，不需要改引擎代码。
6. **GBrain 通过 MCP 调用，不 import 任何 gbrain 代码**：PM-Agent 是 Python，GBrain 是 TypeScript。只通过 `gbrain serve`（stdio MCP）或 HTTP MCP 通信。
7. **所有信封字段必须 JSON 可序列化**：写完 MessageEnvelope 后立即加测试 `json.dumps(envelope.model_dump(), default=str)` 不抛异常。
