# 02 共享黑板与上下文管理深入设计 (Blackboard Pattern RFC)

## 1. 云原生时代的碎片化痛点
在微服务架构中，”牵一发而动全身”是常态。如果不具备全局的高维视角，子代理做出的局部最优决策往往会破坏全局的 API 契约或导致级联雪崩。
2.0 架构通过 **共享黑板 (Blackboard Pattern)** 解决跨 Agent 间的云原生状态同步问题。

## 2. Blackboard 结构设计 (Shared Memory)

黑板是一个驻留在内存中并随时持久化的数据结构，代表了”当前系统对该任务及所处环境的最高维度共识”。在云原生特化下，黑板必须感知微服务拓扑：

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal
from enum import Enum

class MergePolicy(str, Enum):
    “””每个字段声明自己的合并策略，引擎 Merge 时据此分发。”””
    IMMUTABLE = “immutable”           # 创建后不可被子代理修改（如 global_objective）
    LAST_WRITE_WINS = “last_write_wins”  # 后写入覆盖前写入（适合单 owner 字段）
    KEY_PARTITIONED = “key_partitioned”  # Dict 字段按 key 分区，各 Agent 只写自己的 key
    APPEND_DEDUP = “append_dedup”     # 追加并去重（适合 List 类型）
    CONFLICT_ESCALATE = “conflict_escalate”  # 冲突时上报用户裁决

class BlackboardState(BaseModel):
    # 版本追踪
    version: int = Field(default=0, description=”每次 Merge 后自增，用于乐观锁检测”)
    
    # 【云原生高维共识】
    service_topology: Dict[str, Any] = Field(
        default_factory=dict, 
        description=”当前涉及的微服务架构拓扑关系图”,
        json_schema_extra={“merge_policy”: MergePolicy.CONFLICT_ESCALATE}
    )
    api_contracts: Dict[str, str] = Field(
        default_factory=dict,
        description=”核心的 OpenAPI 或 gRPC 契约约束定义”,
        json_schema_extra={“merge_policy”: MergePolicy.CONFLICT_ESCALATE}
    )

    # 业务目标共识
    global_objective: str = Field(
        ..., description=”用户原始意图的规范化描述”,
        json_schema_extra={“merge_policy”: MergePolicy.IMMUTABLE}
    )
    architecture_decisions: List[str] = Field(
        default_factory=list,
        json_schema_extra={“merge_policy”: MergePolicy.APPEND_DEDUP}
    )
    
    # 局部协作与风险预估
    working_drafts: Dict[str, str] = Field(
        default_factory=dict,
        json_schema_extra={“merge_policy”: MergePolicy.KEY_PARTITIONED}
    )
    discovered_risks: List[str] = Field(
        default_factory=list, 
        description=”如 SRE 门卫上报的 '该接口无 RateLimit 将导致雪崩' 等风险”,
        json_schema_extra={“merge_policy”: MergePolicy.APPEND_DEDUP}
    )
    
    # 规则快照
    active_local_rules: List[str] = Field(
        default_factory=list,
        json_schema_extra={“merge_policy”: MergePolicy.APPEND_DEDUP}
    )
```

## 3. 读写机制与并发安全

### 3.1 读权限 — 深拷贝快照 + 版本号

- **Subagents (子代理)** 通过 `Blackboard.get_snapshot()` 获取**深拷贝 (copy.deepcopy)** 只读副本。
- 快照携带当时的 `version` 号，子代理回传结果时必须声明”我基于 version=N 做出的判断”。
- 深拷贝确保即使主控在子代理处理期间修改了 Blackboard，子代理持有的快照不会被污染。

```python
import copy
import asyncio

class Blackboard:
    def __init__(self):
        self._state = BlackboardState(global_objective=””)
        self._write_lock = asyncio.Lock()
    
    def get_snapshot(self) -> tuple[BlackboardState, int]:
        “””返回深拷贝快照及当前版本号。”””
        return copy.deepcopy(self._state), self._state.version
```

### 3.2 写权限 — 单写入者 + 异步锁 + 乐观并发控制

- **仅 Main Agent (主控)** 拥有修改黑板的权限。
- 主控的 Merge 操作通过 `asyncio.Lock` 串行化，防止主控内部多个协程交叉写入。
- 子代理回传的 `MessageEnvelope` 中携带 `based_on_version` 字段。主控在 Merge 前检查：若黑板当前 version 已经超过该值，说明黑板已在子代理工作期间被更新，该结果可能基于过时前提。

```python
    async def merge(self, agent_id: str, payload: dict, based_on_version: int) -> MergeResult:
        async with self._write_lock:
            if based_on_version < self._state.version:
                return MergeResult(
                    status=”STALE”,
                    message=f”Agent {agent_id} 基于 v{based_on_version} 做出判断，”
                            f”但黑板已更新至 v{self._state.version}，需重新执行。”
                )
            # 按字段的 merge_policy 逐一合并
            self._apply_merge_policies(agent_id, payload)
            self._state.version += 1
            return MergeResult(status=”OK”, new_version=self._state.version)
```

### 3.3 Merge 策略引擎

主控 Merge 时，根据每个字段声明的 `merge_policy` 分发处理逻辑：

| MergePolicy | 行为 | 适用场景 |
|---|---|---|
| `IMMUTABLE` | 拒绝任何修改尝试 | `global_objective` 等用户设定字段 |
| `LAST_WRITE_WINS` | 直接覆盖 | 单 owner 的状态字段 |
| `KEY_PARTITIONED` | Dict 按 key 分区写入，各 Agent 只能写 `drafts[self.agent_id]` | `working_drafts` |
| `APPEND_DEDUP` | 追加到 List 并去重 | `discovered_risks`, `architecture_decisions` |
| `CONFLICT_ESCALATE` | 检测到同一 key 被不同 Agent 写入不同值时，挂起并上报用户 | `service_topology`, `api_contracts` |

## 4. 细粒度角色权限管理 (RBAC)

系统在底座层面严格隔离不同特化代理的工具访问能力。比如 `GitOps 编排管家` 能够拉取远程 Helm 仓库配置进行只读分析，但不可直接提交。任何越权调用将触发 `PermissionDenied` 并打回给主控。

## 5. 已知工程权衡

| 权衡点 | 当前选择 | 代价 | 未来优化方向 |
|---|---|---|---|
| `get_snapshot()` 深拷贝 | 每次调用 `copy.deepcopy` | 数十 KB~数百 KB 内存分配 + 毫秒级 CPU | 对于大拓扑可引入 COW (Copy-on-Write) 或分层快照 |
| `asyncio.Lock` 串行写 | 主控内部 Merge 协程串行 | 并发 Merge 请求排队等待 | 可引入批量 Merge (debounce) 减少锁竞争 |
| 过时结果重新执行 | 要求 Agent 基于新快照重跑 | 增加 LLM 调用次数 | 可实现增量 diff 校验：只重新验证受变更影响的字段 |
