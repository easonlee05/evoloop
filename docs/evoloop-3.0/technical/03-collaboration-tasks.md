# 03 Evoloop 3.0 协作与遗留任务认领指南

本文件由 Lane A (3.0 Contracts) 架构师审计并输出，用于梳理当前已完成功能的质量情况，指出目前距离 Evoloop 3.0 全局架构设计中核心能力要求的差距，并建立未尽特性的任务清单供桥接组、原生组与 Adapter 组认领。

---

## 1. 当前完成情况审计 (Audit Summary)

目前已完成 Wave 1 的核心能力并成功通过了 `tests/` 目录下的 16 项新功能单元测试。经检查，已达成的核心技术指标包括：

- **3.0 Contracts 冻结**：各基础对象格式及 Docstring 均已锁定并提供严格的序列化校验。
- **唯一真相源 (SOT) 控制**：在 `ArtifactGraph.validate()` 中落实了 `machine_spec` 唯一性、可追溯性与防止反向越权依赖的代码级硬校验。
- **Acceptance Review 骨架**：实现了 `AdversarialVerificationAgent` (只读对抗性校验子 Agent) 基础扫描框架及 review 结论的 Graph 写入。
- **CLI Adapter 核心命令**：CLI 侧实现了 `compile`, `package`, `acceptance`, `review` 核心命令且均在执行结束前调用了 Graph 自检。

---

## 2. 距离 3.0 架构目标的遗留缺陷 (Architecture Gaps)

根据 [00-global-architecture.md](file:///Users/apple/Desktop/evoloop/docs/evoloop-3.0/architecture/00-global-architecture.md) 对 Control Plane, State/Memory 与 Adapter 的定义，以下架构要求在当前代码实现中**尚未被落实**，需作为后续任务进行开发：

### 2.1 情绪与受挫感侦测 (Frustration Detection) 缺失
* **问题**：在 CLI 的交互循环 (`compile_cmd` / `input()`) 以及 Web 请求交互中，尚未植入情绪分析正则引擎与挂起机制。如果 AI 循环报错或用户连续多次尝试相同修改并受挫（如输入 "wtf", "not working", "fails again" 等），系统会盲目继续轮询重试。

### 2.2 多级上下文压缩 (Context Compaction) 与复水 (Rehydration)
* **问题**：虽然 CLI 端的 Traceback 实现了折叠，但底层的 LLM 会话上下文仍然没有受控。未限制 Tool 输出 Budget（单次调用输入/输出的字符限制），且无 Token 达到阈值 (90%) 触发自动 Compaction（总结 Session State）并进行 Rehydration 复水的能力。

### 2.3 粘性锁存 (Sticky Latch) 缓存最大化机制
* **问题**：在与 LLM 协同的 Adapter 及 Runtime 中，尚未设置 Boolean 锁存器去绝对锁定 System Prompt 和不变的 `machine_spec` 前缀，频繁变化的用户输入仍在影响前缀，未完全实现 Prompt Caching 最大化。

### 2.4 MCP Adapter 缺失 (暂不执行 / DEFERRED)
* **问题**：`app/mcp/` 目录尚不存在，外部 Codex / Claude Code 尚无法以标准 MCP 协议方式调用数字 PM 能力。按 3.0 当前规划，本阶段明确不实现该 Adapter。

---

## 3. 下一步协作任务分发卡 (Task Cards for Claiming)

以下任务卡供桥接组、原生组和 Adapter 组分别认领，认领后请开辟独立 worktree/branch 在各自的独占范围内实现，并提供配套测试：

---

### 【任务卡 D-1】CLI/Web 情绪与受挫感侦测 (Frustration Detection)
* **认领小组**：Lane D (CLI Adapter)
* **独占范围**：[commands.py](file:///Users/apple/Desktop/evoloop/app/cli/commands.py)、[utils.py](file:///Users/apple/Desktop/evoloop/app/cli/utils.py)
* **具体任务**：
  1. 在 [utils.py](file:///Users/apple/Desktop/evoloop/app/cli/utils.py) 中实现 `detect_user_frustration(text: str) -> bool`。使用正则匹配检测 `"wtf"`, `"not working"`, `"fails again"`, `"broken"` 等负面词汇。
  2. 在 [commands.py](file:///Users/apple/Desktop/evoloop/app/cli/commands.py) 中，如果用户在 `compile_cmd` 输入了带有受挫情绪 of 词汇，或者连续 3 次产生相同的测试/编译报错，立刻触发拦截机制：
     - 生成一个非阻塞或阻塞 of `DecisionGate`。
     - 挂起当前 Loop，并在终端或 Web 页面向用户输出步骤指引与澄清提示，杜绝 AI 陷入盲目重试。

---

### 【任务卡 R-1】多级上下文压缩与 Tool Budget 限制
* **认领小组**：Lane F (Runtime & Context Optimization)
* **独占范围**：`app/core/blackboard.py` (若需新建)、`app/workflows/engine.py` (引擎优化)
* **具体任务**：
  1. 对所有的 write/external 类型 Tool 调用限制最大输出字符数 (如 2000 字符)。
  2. 实现超限折叠逻辑，只截取头部/尾部并加上 Compaction 提示，而将完整数据暂存后台以降低 API Payload。
  3. 提供 `Session State` 脱水总结与下轮会话组装 of Rehydration 复水控制流。

---

### 【任务卡 A-1】粘性锁存 (Sticky Latch) 提示词锁定器
* **认领小组**：Lane F (Runtime & Context Optimization)
* **独占范围**：`app/services/llm.py`
* **具体任务**：
  1. 引入 Boolean 锁存变量 `sticky_latch_enabled`。
  2. 保证整个工作会话中，把不可变的 `machine_spec` 定义和 System Prompt 锁定在消息数组首部，把频繁发生变动的数据（如 `DecisionGate` 裁决和最近错误）推入消息流末尾，完全消除前缀微调造成的 Prompt Caching 抖动。

---

### 【任务卡 M-1】3.0 原生 MCP Server Adapter 实现 (暂不执行 / DEFERRED)
* **状态**：本阶段明确不做，推迟至后续 Wave 4 规划中。
* **认领小组**：MCP Adapter 组 (Wave 4)
* **独占范围**：`app/mcp/**`
* **具体任务**：
  1. 创建 MCP Server，注册为具备 3.0 数字 PM 能力 of MCP 的独立服务。
  2. 实现以下 Tools：
     - `get_project_context`
     - `create_requirement`
     - `compile_spec`
     - `get_agent_package`
     - `request_decision`
     - `get_acceptance`
  3. 与核心 Core Contracts 进行底层接线，确保接收到的请求结果经由 `validate()` 检查后输出。
