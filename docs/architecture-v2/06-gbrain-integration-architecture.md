# 06 GBrain 知识库集成架构 (Knowledge Infrastructure Integration)

## 1. 定位：GBrain 是什么，PM-Agent 不需要重复造什么

GBrain 是一个**已经成熟的知识基础设施产品**，具备以下 PM-Agent 不应重复实现的核心能力：

| GBrain 已有能力 | PM-Agent 如果自建的成本 | 结论 |
|---|---|---|
| 四重混合检索（向量 + BM25 + RRF 融合 + 知识图谱遍历） | 需要 pgvector + BM25 + 图引擎 + 排名融合，工程量巨大 | **直接用 GBrain** |
| 合成回答（query 操作）：不返回原始片段，返回带引用的完整答案 + 空白分析 | 需要自建 RAG 后处理链路 | **直接用 GBrain** |
| 知识图谱自动构建：零 LLM 调用从 markdown 中提取实体关系边 | 需要 NER + 关系抽取 + 图存储 | **直接用 GBrain** |
| Schema Packs：动态类型系统，定义知识的目录结构和类型推断 | 需要自建知识分类系统 | **直接用 GBrain** |
| Facts 系统：结构化事实提取、回忆、遗忘 | 需要自建事实管理 | **直接用 GBrain** |
| MCP Server：标准化 MCP 接口，stdio + HTTP OAuth 2.1 | 开箱即用 | **直接对接** |
| Source 隔离：单 brain 多 source，联邦检索或隔离查询 | 需要自建多租户 | **直接用 GBrain** |
| Dream Cycle：定时任务自动整理、充实、合并、修复知识 | 需要自建知识维护 cron | **直接用 GBrain** |

**结论：PM-Agent 的 v2 架构不再需要自建任何知识存储、索引、检索、图谱能力。GBrain 作为外部知识基础设施直接接入。**

---

## 2. 集成方式：通过 MCP 接入

### 2.1 为什么选 MCP 而非直接调库

- GBrain 是 TypeScript/Bun 项目，PM-Agent 是 Python 项目。语言不同，无法直接 import。
- GBrain 提供了标准的 **MCP (Model Context Protocol) Server**，支持 stdio 和 HTTP 两种传输方式。
- MCP 是 Anthropic 定义的标准协议，PM-Agent 的 Agent 可以通过 MCP Client 直接调用 GBrain 的所有 operations。
- 本地开发：`gbrain serve`（stdio）→ 零网络开销
- 生产部署：`gbrain serve --http --port 3131`（HTTP + OAuth 2.1）→ 安全、可远程

### 2.2 接入层架构

```text
PM-Agent (Python)
├── app/core/orchestrator.py        # 主控 Agent
├── app/core/blackboard.py          # 共享黑板
├── app/tools/knowledge_tool.py     # 【新增】GBrain MCP Client 封装
│   ├── query()                     # 调用 GBrain 的 query 操作（合成回答）
│   ├── search()                    # 调用 GBrain 的 search 操作（原始片段）
│   ├── get_page()                  # 获取具体知识页
│   ├── put_page()                  # 写入新知识页（法则入库时使用）
│   ├── extract_facts()             # 提取结构化事实
│   ├── recall()                    # 回忆已存事实
│   ├── think()                     # 深度推理
│   └── find_contradictions()       # 检测矛盾
└── app/tools/gbrain_mcp_client.py  # 【新增】MCP 通信底层
    ├── connect()                   # 建立 stdio/HTTP 连接
    ├── call_tool()                 # 调用 GBrain operation
    └── disconnect()                # 断开连接
```

### 2.3 Tool 注册

GBrain 相关能力以 Tool 形式注册到 PM-Agent 的 ToolPolicy 白名单中：

```python
# app/tools/knowledge_tool.py
from app.tools.gbrain_mcp_client import GBrainMCPClient

class KnowledgeTool:
    """封装 GBrain MCP 调用为 PM-Agent Tool 接口。"""
    
    def __init__(self, client: GBrainMCPClient):
        self.client = client
    
    async def query(self, question: str, source: str = None) -> dict:
        """调用 GBrain query 操作，获取合成回答 + 引用 + 空白分析。"""
        params = {"query": question, "detail": "high"}
        if source:
            params["source"] = source
        return await self.client.call_tool("query", params)
    
    async def search(self, query: str, limit: int = 10) -> dict:
        """调用 GBrain search 操作，获取原始匹配片段。"""
        return await self.client.call_tool("search", {"query": query, "limit": limit})
    
    async def put_page(self, slug: str, content: str, page_type: str) -> dict:
        """写入知识页（法则入库时使用）。"""
        return await self.client.call_tool("put_page", {
            "slug": slug,
            "content": content,
            "type": page_type
        })
    
    async def find_contradictions(self, slug: str) -> dict:
        """检测某页知识与已有知识的矛盾。"""
        return await self.client.call_tool("find_contradictions", {"slug": slug})
```

---

## 3. 在 PM-Agent 各层的接入点

### 3.1 Blackboard 上下文加载阶段

**何时调用**：DAG 执行前，主控初始化 Blackboard 时。

**做什么**：根据用户目标，向 GBrain 发起 `query` 操作，获取相关知识上下文，写入 Blackboard 的知识字段。

```python
# 主控初始化上下文时
knowledge_result = await knowledge_tool.query(
    question=user_objective,
    source="rules"  # 从法则 source 检索
)
blackboard.knowledge_context = knowledge_result["answer"]
blackboard.knowledge_citations = knowledge_result["citations"]
blackboard.knowledge_gaps = knowledge_result["gaps"]  # GBrain 会告诉你它不知道什么
```

**GBrain 的 gap analysis 特性**在这里特别有价值：它会明确告诉主控"关于这个问题，我没有覆盖到的知识有哪些"，主控可以据此决定是否需要要求用户补充材料。

### 3.2 Subagent 执行阶段

**何时调用**：子代理在执行任务过程中需要查询具体的事实或规则。

**做什么**：子代理通过 ToolPolicy 授权的 `knowledge.query` / `knowledge.search` Tool 向 GBrain 检索。

```python
# 子代理（如 SRE 门卫）在 execute() 中
async def execute(self, envelope: MessageEnvelope) -> MessageEnvelope:
    # 通过受控 Tool 查询限流策略相关知识
    rate_limit_rules = await self.call_tool("knowledge.query", {
        "question": f"关于 {service_name} 的限流和熔断策略要求"
    })
    # 基于查询结果做出判断...
```

**注意**：子代理不能直接 `put_page` 写入 GBrain。写入必须通过主控审核后，由专门的法则入库流程完成。

### 3.3 规则生命周期（与 03 文档的关系）

03 文档定义的"法则生命周期"（诞生 → 冲突检测 → 淘汰）在 GBrain 集成后的对应关系：

| 03 文档定义的概念 | GBrain 中的对应 | 谁负责 |
|---|---|---|
| 法则的存储 | GBrain 的 `pages` 表 + `source="rules"` | GBrain |
| 法则的检索 | GBrain 的 `query` / `search` 操作（四重混合检索） | GBrain |
| 法则的 Namespace 隔离 | GBrain 的 `source` 机制（Global=全局source, Local=业务source） | GBrain |
| 法则的冲突检测 | GBrain 的 `find_contradictions` 操作 | GBrain |
| 法则的版本追踪 | GBrain 页面自带 version + 变更历史 | GBrain |
| 法则的淘汰决策逻辑 | PM-Agent 的 RuleService（CRITICAL/STANDARD/DEPRECATED 分级） | **PM-Agent** |
| 法则的写入（入库） | PM-Agent 审核通过后调用 GBrain `put_page` | PM-Agent 调 GBrain |
| 法则的归档 | PM-Agent 决定后调用 GBrain `delete_page`（软删除） | PM-Agent 调 GBrain |

**关键区分**：
- **GBrain 负责存储和检索**（它是知识基础设施）
- **PM-Agent 负责决策逻辑**（何时创建、何时淘汰、冲突时如何仲裁）

### 3.4 Diff 提炼与法则入库

当用户编辑终稿后，PM-Agent 的 Diff 流程提炼候选法则。候选法则经人工审核通过后，写入 GBrain：

```python
# 法则入库流程
async def approve_and_store_rule(rule_content: str, rule_meta: dict):
    slug = f"rules/{rule_meta['namespace']}/{rule_meta['slug']}"
    
    # 1. 先检测与已有法则是否矛盾
    # 利用 GBrain 的 find_contradictions 能力
    contradictions = await knowledge_tool.find_contradictions(slug)
    if contradictions["found"]:
        # 上报用户裁决
        raise ConflictDetectedError(contradictions)
    
    # 2. 写入 GBrain
    await knowledge_tool.put_page(
        slug=slug,
        content=rule_content,
        page_type="rule"
    )
```

---

## 4. 与 v2 架构中"重复造轮子"风险的消解

### 4.1 Blackboard vs GBrain — 不冲突，各管各的

| 关注点 | Blackboard | GBrain |
|---|---|---|
| 生命周期 | 单次任务内（任务结束即销毁） | 持久化（跨任务、跨会话） |
| 数据性质 | 运行时状态（草稿、风险发现、当前共识） | 长期知识（法则、事实、规则） |
| 读写模型 | 内存级，asyncio.Lock 保护 | 数据库级，支持并发 |
| 检索能力 | 无检索，只是结构化状态 | 四重混合检索 + 图遍历 + 合成 |

**结论**：Blackboard 管"这次任务的临时工作状态"，GBrain 管"跨所有任务的长期知识资产"。两者互补，不重叠。

### 4.2 03 文档的"规则引擎" vs GBrain — 决策逻辑 vs 存储检索

03 文档定义的 `RuleService` 是**淘汰决策逻辑**（CRITICAL/STANDARD/DEPRECATED 分级、LRU 衰减计算、人工确认流程），不是知识存储。

法则的物理存储和检索全部委托给 GBrain。PM-Agent 不需要自建向量库、不需要自建检索管线、不需要自建知识图谱。

### 4.3 Context Slice 的知识注入 — GBrain 如何服务于 DAG 执行

主控在生成 DAG 后、为每个节点裁切 `context_slice` 时，可以根据节点的 `SlotContract.required_context_keys` 中是否包含知识相关字段，决定是否向 GBrain 发起针对性检索：

```python
# 主控为每个 DAG 节点准备 context_slice
async def prepare_context_slice(self, node: DAGNode) -> dict:
    contract = self.registry.get_contract(node.agent_slot)
    slice_data = {}
    
    for key in contract.required_context_keys:
        if key in self.blackboard.fields:
            slice_data[key] = self.blackboard.get_field(key)
        elif key.startswith("knowledge_"):
            # 需要从 GBrain 检索
            query = self._derive_query_from_node(node, key)
            result = await self.knowledge_tool.query(query)
            slice_data[key] = result["answer"]
    
    return slice_data
```

---

## 5. GBrain Source 规划

PM-Agent 的 GBrain 实例应配置以下 source 分区：

| Source ID | 用途 | 写入者 | 读取者 |
|---|---|---|---|
| `rules-global` | 全局强制法则（安全红线、合规要求） | 审核流程（人工确认后写入） | 所有 Agent |
| `rules-domain` | 领域特化法则（云原生/电商等） | 审核流程 | 已加载对应扩展包的 Agent |
| `knowledge-platform` | 平台事实（页面规则、字段定义） | 管理员导入 | 所有 Agent |
| `knowledge-business` | 业务规则（流程、准入条件） | 管理员导入 | 所有 Agent |
| `archive` | 已归档/废弃的法则 | RuleService 淘汰流程 | 仅管理员审计 |

通过 GBrain 的 `source` 隔离 + 联邦检索机制：
- 检索时可以指定 `source="rules-global"` 精确查询
- 也可以不指定 source，GBrain 会联邦检索所有 source 并融合结果

---

## 6. 降级策略

当 GBrain 不可用时：

1. PM-Agent 检测到 MCP 连接断开或超时
2. Blackboard 标记 `knowledge_degraded = true`
3. 主控使用本地缓存的最近一次知识快照（GBrain 支持 `list_pages` 导出）
4. 所有 Agent 输出中附加 disclaimer："知识库不可用，以下判断可能基于过时信息"
5. Reviewer 门禁增加"降级知识风险"检查项
6. GBrain 恢复后，主控重新拉取最新知识，刷新 Blackboard

---

## 7. 不需要 PM-Agent 自建的能力清单（避免重复造轮子）

以下能力 **不要** 在 PM-Agent 代码库中实现，直接通过 GBrain MCP 调用：

- ❌ 向量嵌入生成与存储
- ❌ 关键词索引（BM25）
- ❌ 混合检索与排名融合
- ❌ 知识图谱构建与遍历
- ❌ 实体关系抽取（NER）
- ❌ 知识去重与合并
- ❌ 法则的物理存储和版本追踪
- ❌ 知识矛盾检测
- ❌ 知识快照导出

以下能力 **由 PM-Agent 自建**（GBrain 不覆盖）：

- ✅ 法则淘汰决策逻辑（CRITICAL/STANDARD/DEPRECATED + LRU 衰减）
- ✅ Blackboard 运行时状态管理
- ✅ DAG 编排与执行
- ✅ Agent 间通信协议
- ✅ 前端共创交互
- ✅ 扩展包插槽注册与覆盖
- ✅ 人工审核流程控制
