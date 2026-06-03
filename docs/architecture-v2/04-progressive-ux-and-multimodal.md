# 04 前端体验与多模态架构 (Progressive UX & Multi-modal)

## 1. 应对大模型黑盒的焦虑

在 2.0 的动态路由架构下，主控协调多个 Subagent 往往需要漫长的请求周期。如果前端缺乏有效的进展透出，将严重挫伤用户的信任。

## 2. 工作流透视窗 (Workflow Transparency)

基于后端的 `Event Bus`，前端通过 SSE (Server-Sent Events) 渲染实时的路由树日志：

- **节点状态可视化**：前端动态绘制主控生成的 DAG (有向无环图)，实时点亮正在执行的节点。
- **对话旁听席**：用户可以看到信封协议的流转（如：“`[Main Agent]` -> `[QA Subagent]` 派发安全检测任务...”）。

## 3. 渐进式共创与随时接管 (Progressive Steering & Takeover)

打破 1.0 版本只能死等引擎跑完或遇到严重分歧才请求 Arbiter 的模式：

### 3.1 Pause & Intervene（暂停与干预）

用户可在前端点击”暂停”，强行阻断当前的 DAG 走向。暂停后用户可以：
- 查看当前各节点状态
- 修改尚未执行的节点参数
- 删除不需要的下游节点
- 确认继续执行

### 3.2 Role Takeover（角色接管）

用户可以代替某个陷入困境或误判的 Subagent，直接向主控注入正确的事实。

**Takeover 的 Checkpoint 机制**：

为避免并发状态污染，Takeover 只能在**节点边界**（即一个节点完成、下一个节点启动前）发生，而非任意时刻。完整流程：

1. **用户发起 Takeover 请求**：前端向 Event Bus 发送 `TakeoverRequest(target_agent_id)`
2. **全局挂起**：主控收到请求后，向 Bus 广播 `SUSPEND` 信号，所有正在运行的并行 Agent 暂停执行（当前 LLM 调用允许完成，但结果暂不写入 Blackboard）
3. **状态冻结**：Blackboard 标记为 frozen，拒绝一切 Merge 操作
4. **用户注入**：用户通过前端 UI 输入正确信息，主控将其直接写入 Blackboard（frozen 期间仅主控在用户授权下可写）
5. **脏节点传播**：主控执行 `DirtyPropagation` 算法（见 §3.3），标记所有依赖被修改数据的下游节点为 STALE
6. **恢复执行**：Blackboard 解除 frozen，主控恢复 DAG 执行：
   - 已完成且不在 STALE 集合中的节点 → 保留结果
   - 被标记为 STALE 的节点 → 丢弃旧结果，基于新 Blackboard 快照重新执行
   - 尚未执行的节点 → 正常调度

### 3.3 脏节点传播算法 (Dirty Propagation)

当用户 Takeover 修改了 Blackboard 中的某些字段后，需要判断哪些已完成的节点结果需要作废：

```
输入：modified_fields = 用户修改的 Blackboard 字段集合
输出：stale_nodes = 需要重新执行的节点集合

对 DAG 中每个已完成的节点 N：
    N 的 context_slice 依赖了哪些 Blackboard 字段？（由 SlotContract.required_context_keys 确定）
    如果 N 依赖的字段 ∩ modified_fields ≠ 空集：
        标记 N 为 STALE
        递归标记 N 的所有下游节点为 STALE（因为它们可能使用了 N 的输出）
```

这类似编译器的增量编译：修改一个源文件后，只重新编译依赖它的文件，而非全部重新编译。

## 4. 扩展包加载体验 (Onboarding Wizard & Plugin Market)

为了解决“可插拔领域框架”中扩展包的挂载问题，PM-Agent 放弃了高算力损耗的“自动嗅探激活”，全面采用具有 **100% 确定性** 的向导模式：

### 4.1 工作空间初始化 (Workspace Onboarding)
- 用户首次创建项目或 Workspace 时，必须通过 UI 向导明确选择其所在的行业（例如：`云原生底座`、`泛电商 SaaS`）。
- 该选择将被固化到当前 Workspace 的环境变量中，引擎**零延迟**地加载对应的 `[云原生扩展包]`，屏蔽了意图分类分类器的首包延迟损耗。

### 4.2 防污染与心智建设
- 固定的扩展包环境有效消除了 LLM 的认知负载和跨界幻觉污染。
- 引入类似 VSCode 的**插件市场 (Plugin Store)** 视图。用户可以直观地看到系统已装载了 `[SRE 门卫]` 和 `[可观测架构师]`，建立了强大的“专业工具”心智，而非不可控的盲盒。

## 5. 多模态视觉能力的初步集成

PM 和运营的交互强依赖于视觉媒介，文本表达难以完全还原界面意图。

- **V2 首期范围**：接入具备 Vision 能力的 LLM (如 GPT-4V, Claude-3.5-Sonnet)，支持用户上传图片/截图。
- **处理链路**：由专职的 `Vision_Subagent` 负责对图片进行 OCR 提取、界面元素结构化，以及与原始需求的对比。
- **未来展望 (V3/V4)**：通过 Figma MCP (Model Context Protocol) 等机制直连设计稿平台，实现自动校验和深度集成。
