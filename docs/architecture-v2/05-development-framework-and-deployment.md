# 05 工程开发框架与部署架构规范 (Development Framework & Deployment)

## 1. 核心工程设计原则

在 PM-Agent 2.0 的开发阶段，为了最大化单人（或小团队）的研发效率，降低运维心智负担，同时确保系统具备企业级的扩展深度，系统采用 **“模块化单体 (Modular Monolith)”** 编写框架与 **“单机单进程”** 部署模式。

其核心思想为：**物理单体，逻辑多态，契约隔离，单机运行。**

---

## 2. 代码库颗粒度与目录结构

为支持扩展包的“插槽覆盖与动态追加”机制，代码结构必须达到文件级别的物理隔离。扩展包应以独立文件夹的形式组织，不得污染核心引擎目录。

### 2.1 推荐目录树

```text
evoloop/
├── app/
│   ├── core/                    # 【核心引擎控制面 - 物理高内聚】
│   │   ├── orchestrator.py      # 主控 Orchestrator 引擎，负责生成 DAG
│   │   ├── blackboard.py        # 共享黑板（内存级状态持久化）
│   │   ├── envelope.py          # 严格的 MessageEnvelope Pydantic Schema
│   │   └── registry.py          # 动态反射、扩展包加载与插槽覆盖注册表
│   │
│   ├── agents/                  # 【专家 Agent 实现层 - 极细物理颗粒度】
│   │   ├── base.py              # BaseSubagent 抽象基类，规范标准 execute 接口
│   │   │
│   │   ├── core_pack/           # 基础通用专家包
│   │   │   ├── ux_critic.py     # 槽位 UX_Critic：通用交互体验专家
│   │   │   ├── copywriter.py    # 槽位 Copywriter：通用文案代理
│   │   │   ├── biz_analyst.py   # 槽位 Biz_Analyst：通用业务分析师
│   │   │   └── deploy_gen.py    # 槽位 Deploy_Gen：通用部署生成器
│   │   │
│   │   └── cloud_native/        # 云原生特化扩展包（物理独立，防止认知污染）
│   │       ├── microservice.py  # 覆盖槽位 Biz_Analyst：微服务边界分析师
│   │       ├── gitops.py        # 覆盖槽位 Deploy_Gen：GitOps 交付编排管家
│   │       ├── sre_guard.py     # 追加槽位 Reliability_Guard：SRE 容灾门卫
│   │       └── observability.py # 追加槽位 Observability_Architect：可观测性架构师
│   │
│   └── api/                     # 【暴露接口层】
│       └── server.py            # FastAPI 单机服务接口，提供 SSE 总线事件流
```

### 2.2 专家文件开发规范

为了实现无缝插槽替换，每一个 Agent 的开发必须遵循 **”一代理一文件”** 和 **”声明式绑定”** 原则：

1.  **物理隔离**：每个 Agent（如 `sre_guard.py`）是一个独立的文件，不允许在单个文件内编写多个 Agent 的业务逻辑。
2.  **继承与接口规范**：统一继承 `BaseSubagent`，重写 `execute(self, envelope: MessageEnvelope)` 异步方法。
3.  **插槽声明与契约版本 (Metadata)**：在类属性中显式声明对应的槽位名称、加载行为，以及实现的 SlotContract 版本：
    ```python
    # 示例：app/agents/cloud_native/microservice.py
    from app.agents.base import BaseSubagent

    class MicroserviceAnalyst(BaseSubagent):
        slot_name = “Biz_Analyst”          # 指定目标插槽
        action_type = “OVERRIDE”           # 覆盖（OVERRIDE）基础插槽，若为新增专家则为 APPEND
        contract_version = “2.0”           # 声明实现的 SlotContract 版本
        
        async def execute(self, envelope: MessageEnvelope) -> MessageEnvelope:
            # 1. 从信封的 context_slice 获取高维拓扑与契约
            # 2. 调用受控 Tool 沙箱分析
            # 3. 返回符合 expected_output_format 的新信封
            pass
    ```

4.  **Registry 加载时的静态校验**：Agent 注册时，Registry 自动校验：
    - `contract_version` 是否与当前 Slot 的 SlotContract 兼容
    - OVERRIDE Agent 的输出 schema 是否满足 SlotContract 声明
    - 不兼容则拒绝加载，输出明确错误信息

---

## 3. 运行期内存级通信

在单机部署下，为了消除不必要的网络通信开销和链路追踪成本，Agent 之间的交互通过**内存总线**进行：

1.  **事件总线 (Event Bus)**：底层使用 Python 的 `asyncio.Queue`（异步队列）实现非阻塞的消息发布与订阅，完全在单进程内存空间中流转。Bus 同时维护 `SessionBudgetTracker`，追踪每个子任务会话的 hop_count 和 llm_calls 预算。
2.  **上下文共享 (Blackboard Memory)**：共享黑板作为一个全局单例驻留在内存中。子代理调用 `get_snapshot()` 时获取**深拷贝 (copy.deepcopy)** 只读副本及版本号，主控通过 `asyncio.Lock` 保护的 Merge 接口写入，实现乐观并发控制（详见 02 文档）。
3.  **JSON 可序列化约束**：虽然在同一进程中传递对象，所有 `MessageEnvelope` 字段必须始终满足 JSON 可序列化要求。CI 中强制包含序列化测试。这确保未来微服务演进时无需逐一排查不可序列化字段。

---

## 4. 面向未来的物理微服务演进路线

尽管目前采用单机单进程部署，但由于我们已经在 **通信协议 (01)** 中强制了严格的 `MessageEnvelope` 信封契约，未来如果因算力（如某些 Agent 需要独占专用的 GPU/推理服务器）或团队协作需要将其拆分为独立微服务，可以实现 **零内核代码改动** 的平滑演进：

```mermaid
graph TD
    subgraph 单机单进程Monolith (当前状态)
        Main1[主控 Orchestrator] -->|内存 asyncio.Queue| LocalAgent[本地 SRE Agent 实例]
    end

    subgraph 微服务演进 (未来状态)
        Main2[主控 Orchestrator] -->|发送信封| Adapter[网络代理 SRE Adapter]
        Adapter -->|HTTP / gRPC / Webhook| RemoteVM[远程 GPU VM / Serverless]
        RemoteVM -->|执行微服务| RemoteAgent[物理微服务 SRE Agent]
        RemoteAgent -->|回传信封| Adapter
    end
```

### 微服务化拆步指南：
1.  **剥离专家**：将特定的专家类（如 `sre_guard.py`）移出单体仓库，包装成一个极简的 FastAPI 接口服务，部署在任意服务器上。
2.  **注入 Adapter**：在单体系统的 `app/agents/cloud_native/` 目录下，保留原有的 `sre_guard` 类，但将其实现修改为 `NetworkAdapterSubagent`。
3.  **透明代理**：该 Adapter 同样继承 `BaseSubagent` 并暴露出相同的接口。在 `execute` 时，它仅做一件事：**将信封对象序列化为 JSON，通过 HTTP/gRPC 发送给远端微服务，并将回传结果反序列化为信封返回。**
4.  **结果**：主控引擎不需要修改任何一行路由和状态逻辑，无缝完成了物理微服务化演进。
