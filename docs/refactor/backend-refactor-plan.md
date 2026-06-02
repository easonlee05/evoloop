# 后端重构设计文档：PM-Agent 双产品线平台

## 1. 背景与目标

当前仓库经历了多轮功能叠加：操作手册生成、PRD 虚拟群聊、Web Mock、文件仓库、Memory、GBrain 架构文档等能力混在同一套入口和编排里。继续在旧结构上局部修改，会让废弃代码、Mock 逻辑和真实流程继续互相污染。

本次重构目标不是简单清理代码，而是把系统重建为一个以 PM Agent 为主线的文档/方案共创平台。首批产品线保留两类能力：

1. **操作手册编写**：把用户上传的材料、平台知识和格式规范转化为可交付的 B 端 Markdown 操作手册。
2. **PRD 编写**：通过 PM、Tech、QA、Reviewer 的多角色攻防，把业务诉求转化为结构化 PRD。

新架构必须给后续功能预留扩展位。未来新增功能时，应新增任务定义和少量策略代码，而不是复制一套 Orchestrator。

## 2. 协作边界

本次重构由两个 AI 协作完成：

| 参与方 | 职责 | 不负责 |
|---|---|---|
| Codex | 后端重构、任务引擎、Agent 协议、API/SSE 协议、存储与知识接口、旧后端清理 | 前端视觉实现、复杂交互细节 |
| Antigravity | 前端工作台、任务创建/直播/仲裁/文件浏览/终稿编辑 UI、前端状态管理 | 后端编排、Agent Prompt、模型调用实现 |

前后端通过稳定 API 和事件协议协作。前端不直接调用模型，不直接写知识库；后端不硬编码前端页面状态，只输出可订阅事件和可读写资源。

## 3. 重构原则

1. **新内核优先**：先建立干净的新内核，再迁移旧资产；不要在旧 Orchestrator 上继续打补丁。
2. **任务类型插件化**：`manual` 和 `prd` 都是 `TaskDefinition`，未来新增功能也走同一机制。
3. **PM 主笔，角色攻防**：PM 负责主方案和终稿收敛；Tech、QA、Reviewer 提供约束、反驳和门禁。
4. **统一事实基线**：每个任务只生成一个 `TaskContext`，所有 Agent 共享，避免各自检索导致事实冲突。
5. **人类裁决优先**：用户打断和仲裁结果写入上下文，后续 Agent 必须服从。
6. **事件流透明**：所有关键状态、Agent 发言、门禁结果、仲裁请求都通过事件流暴露给前端。
7. **产物与运行态分离**：任务运行状态、事件、输出文件、知识法则分别管理，不互相混写。
8. **旧资产选择性迁移**：迁移 prompt、格式规范、架构文档、文件隔离经验；删除废弃流程和 Mock 逻辑。

## 4. 目标能力范围

### 4.1 首期必须支持

- 创建 `manual` 任务。
- 创建 `prd` 任务。
- 任务运行中持续输出事件流。
- PM、Tech、QA、Reviewer 按统一协议协作。
- 任务需要用户裁决时暂停，收到裁决后恢复。
- 生成 Markdown 产物并可由前端读取。
- 支持用户隔离的文件目录。
- 保留操作手册格式规范。
- 后端提供清晰 API，供 Antigravity 重做前端对接。

### 4.2 首期不做或降级

- 不在第一阶段实现完整 GBrain 服务；先保留 `KnowledgePort`，可以接本地文件或空检索。
- 不在第一阶段实现复杂权限系统；保留 username/workspace 隔离参数。
- 不追求完全兼容旧 CLI 行为；CLI 可作为薄入口调用新 `TaskService`。
- 不保留 Web Mock 分支；演示数据应独立为 seed/dev fixture。
- 不自动写入长期法则；Diff 先输出候选法则，人工审核入库作为后续阶段。

## 5. 目标目录结构

建议重建 `app/`，旧代码在迁移期移动到 `legacy/` 或依赖 git 历史追溯。

```text
app/
  api/
    server.py              # HTTP/SSE API 入口
    schemas.py             # 请求/响应 DTO

  core/
    task.py                # Task、TaskType、TaskStatus、TaskDefinition
    context.py             # TaskContext、KnowledgeContext、UserDecision
    events.py              # Event 类型、事件序列化
    artifacts.py           # Artifact、ArtifactStore 协议
    tools.py               # ToolSpec、ToolCall、ToolResult、ToolPolicy
    ports.py               # LLMPort、KnowledgePort、StoragePort、ClockPort
    errors.py              # 领域错误

  agents/
    base.py                # Agent 基类与 LLM 调用封装
    pm.py                  # PM Agent
    tech.py                # Tech Lead Agent
    qa.py                  # QA Agent
    reviewer.py            # Reviewer Agent
    writer.py              # 终稿 Writer Agent
    prompts/
      manual.py            # 操作手册任务 Prompt 片段
      prd.py               # PRD 任务 Prompt 片段
      common.py            # 共享 Prompt 片段

  workflows/
    engine.py              # 通用任务引擎
    steps.py               # WorkflowSpec、WorkflowStep、StepResult
    definitions.py         # 任务定义注册表
    manual.py              # manual TaskDefinition
    prd.py                 # prd TaskDefinition
    policies.py            # 轮次策略、门禁策略、仲裁策略

  services/
    task_service.py        # 创建/运行/恢复/取消任务
    event_service.py       # 事件订阅、缓冲、回放
    file_service.py        # 用户隔离文件读写、备份、导出
    knowledge_service.py   # 本地/GBrain 知识检索适配
    diff_service.py        # 终稿 diff 与候选法则提炼
    tool_service.py        # Tool 注册、权限校验、调用审计

  runtime/
    config.py              # 环境变量、路径、模型配置
    logging.py             # 日志与 console 适配

  main.py                  # CLI 薄入口
```

如需保留前端静态资源，建议拆到：

```text
frontend/
  ...                      # Antigravity 负责
```

避免继续把大型 HTML/React 单文件塞进 `app/static/`。

## 6. 核心领域模型

### 6.1 TaskDefinition

`TaskDefinition` 是后续扩展的核心。新增功能时优先新增定义，而不是新增一套编排器。

```python
@dataclass
class TaskDefinition:
    type: str
    display_name: str
    input_schema: type
    context_builder: ContextBuilder
    agents: AgentTeamSpec
    round_policy: RoundPolicy
    gate_policy: GatePolicy
    output_spec: OutputSpec
    workflow: WorkflowSpec
    tool_policy: ToolPolicy
```

`manual` 和 `prd` 的差异应主要体现在：

- 输入字段不同。
- 上下文构建策略不同。
- Agent prompt 侧重点不同。
- 输出文件结构不同。
- Reviewer 门禁不同。

### 6.2 TaskContext

```text
TaskContext
  task_id
  task_type
  username
  goal
  user_constraints
  source_materials
  knowledge_context
  format_spec
  round_history
  open_disputes
  user_decisions
  gate_results
  artifacts
  degradation_state
```

约束：

- Agent 只能读取同一个 `TaskContext`。
- 用户裁决写入 `user_decisions` 后优先级高于 Agent 推测。
- `round_history` 必须保留每轮 PM、Tech、QA、Reviewer 的关键输出，方便前端展示和后续 Diff。

### 6.3 Event

事件是前端协作的唯一实时协议。

```text
Event
  id
  task_id
  type
  role
  status
  payload
  created_at
```

首期事件类型：

| 事件 | 说明 |
|---|---|
| `task.created` | 任务创建完成 |
| `task.started` | 任务开始运行 |
| `context.loaded` | 上下文加载完成 |
| `round.started` | 新一轮攻防开始 |
| `agent.message.started` | Agent 开始发言 |
| `agent.message.delta` | Agent 流式输出片段 |
| `agent.message.completed` | Agent 发言结束 |
| `gate.started` | Reviewer 门禁开始 |
| `gate.completed` | Reviewer 门禁完成 |
| `arbitration.requested` | 需要用户仲裁 |
| `arbitration.applied` | 用户裁决已应用 |
| `artifact.created` | 产物生成或更新 |
| `workflow.step.started` | Workflow 步骤开始 |
| `workflow.step.completed` | Workflow 步骤完成 |
| `workflow.step.failed` | Workflow 步骤失败 |
| `tool.call.started` | Tool 调用开始 |
| `tool.call.completed` | Tool 调用成功 |
| `tool.call.failed` | Tool 调用失败 |
| `tool.call.denied` | Tool 权限拒绝 |
| `task.completed` | 任务完成 |
| `task.failed` | 任务失败 |
| `task.cancelled` | 任务取消 |

前端必须基于事件驱动 UI，不应解析后端日志文本。

## 7. 通用任务引擎

详细 Workflow 与 Tool 横切架构见 `docs/architecture/05-workflow-tool-architecture.md`。本节只定义重构落地时必须遵守的引擎协议。

`WorkflowEngine` 负责所有任务类型的共同行为：

```text
create task
  -> validate input
  -> build TaskContext
  -> load knowledge
  -> run rounds
  -> request arbitration if needed
  -> run gate
  -> write artifacts
  -> close task
```

引擎不关心具体文档类型，只调用 `TaskDefinition` 提供的策略。

### 7.1 WorkflowSpec 与 StepResult

每个任务类型必须声明自己的 `WorkflowSpec`。引擎只解释步骤，不硬编码 `manual` 或 `prd` 的业务路径。

```text
WorkflowSpec
  name
  version
  steps[]
    id
    type: context | agent | gate | arbitration | artifact | diff | checkpoint
    title
    role
    input_keys
    output_keys
    allowed_tools
    retry_policy
    pause_policy
```

每个步骤必须返回统一 `StepResult`：

```text
StepResult
  step_id
  status: succeeded | failed | blocked | needs_arbitration | cancelled
  summary
  outputs
  events[]
  tool_calls[]
  error
  next_step_id
```

约束：

- 步骤不得直接改全局状态，只能通过 `StepResult.outputs` 和服务接口提交变更。
- `needs_arbitration` 是正常暂停状态，不是失败。
- 每个步骤完成后必须写 checkpoint，恢复时从最后一个成功 checkpoint 继续。
- 写产物、读材料、检索知识、提炼 Diff 都必须经由 Tool，不能在 Agent 内直接读写。

### 7.2 标准轮次协议

```text
Round N
  1. PM 输出方案/大纲版本 Vn
  2. Tech 输出挑战清单
  3. PM 吸收 Tech 后修订 Vn.1
  4. QA 输出异常与验收挑战
  5. PM 吸收 QA 后修订 Vn.2
  6. 引擎判断是否收敛
```

收敛条件：

- 没有未处理的 Blocking 技术问题。
- 没有未处理的致命异常用例。
- PM 明确说明每条关键反对意见的处理结果。
- 方案没有违反用户裁决。
- Reviewer 门禁可以进入审查。

最大轮次默认为 3。达到最大轮次仍不收敛时，引擎生成 `DisputePackage` 并暂停任务。

### 7.3 仲裁协议

```text
DisputePackage
  title
  background
  decision_needed
  options[]
    label
    pm_position
    tech_position
    qa_position
    benefit
    cost
    risk
    recommended
  impact_after_decision
```

前端展示分歧包，用户选择或输入裁决。后端收到裁决后：

1. 记录原文裁决。
2. 写入 `TaskContext.user_decisions`。
3. 触发 PM 基于裁决重写方案。
4. 继续进入门禁或下一轮。

### 7.4 Tool 调用协议

Agent 和 Workflow 需要外部能力时必须通过 `ToolService`。Tool 先注册，再按任务类型、角色和步骤授权。

```text
ToolSpec
  name
  version
  description
  input_schema
  output_schema
  side_effect: none | read | write | external
  required_permissions[]
```

```text
ToolPolicy
  task_type
  role
  step_id
  allowed_tools[]
  max_calls_per_step
  require_user_approval_for[]
```

首期 Tool 清单：

| Tool | 类型 | 用途 |
|---|---|---|
| `material.read` | read | 读取用户上传材料摘要或原文片段 |
| `material.parse` | read | 解析上传材料为结构化材料包 |
| `knowledge.retrieve` | read | 检索 GBrain 或本地知识快照 |
| `artifact.read` | read | 读取已有产物供审查或 Diff 使用 |
| `artifact.write` | write | 写 Markdown 产物并记录版本 |
| `artifact.backup` | write | 用户编辑或重写前备份旧版本 |
| `format.validate` | none | 校验格式红线和结构要求 |
| `diff.extract_rules` | write | 生成候选法则，不直接入库 |
| `event.emit` | write | 输出结构化事件 |

禁止 Agent 调用任意 shell、任意网络请求、任意文件路径读取。新增 Tool 必须先进入注册表和 `TaskDefinition.tool_policy` 白名单。

## 8. 两条产品线定义

### 8.1 操作手册编写：`manual`

输入：

- 模块名。
- 上传材料。
- 可选补充要求。
- 可选知识库范围。
- 用户名或工作区。

角色分工：

| 角色 | 职责 |
|---|---|
| PM | 识别模块目标、用户路径、文档拆分方案和待澄清点 |
| Tech | 校正云原生/平台技术事实，指出架构或术语风险 |
| QA | 从可执行性、异常路径、遗漏操作角度挑战文档方案 |
| Reviewer | 执行格式红线、材料映射、去内部痕迹、重复章节等门禁 |
| Writer | 输出最终 Markdown 操作手册 |

输出：

```text
{module}操作手册/
  模块概览.md
  {操作场景}.md
  平台体验与功能改进意见.md
  _evidence/
    task_context.json
    rounds.md
    gate_results.md
```

迁移资产：

- `app/格式.md` 作为 `manual` 的格式规范。
- 旧 `InternAgent`、`ReviewerAgent`、`ExpertAgent` prompt 中的有效规则。
- `file_store.py` 的用户隔离和 git/local backend 思路。

### 8.2 PRD 编写：`prd`

输入：

- 产品特性/业务域。
- 业务诉求。
- 约束、偏好和已有材料。
- 用户名或工作区。

角色分工：

| 角色 | 职责 |
|---|---|
| PM | 业务目标拆解、主流程、功能边界、版本计划、最终 PRD 主笔 |
| Tech | 服务边界、数据流、一致性、容量、依赖、降级、解耦挑战 |
| QA | 异常流、边界条件、脏数据、并发、验收标准挑战 |
| Reviewer | 检查目标一致性、架构完整性、异常完整性、风险透明度、可交付性 |
| Writer | 输出结构化 PRD Markdown |

输出：

```text
{feature}产品文档/
  PRD.md
  架构评审记录.md
  风险与验收清单.md
  _evidence/
    task_context.json
    rounds.md
    gate_results.md
```

迁移资产：

- 旧 `pm_agent.py`、`tech_lead_agent.py`、`qa_agent.py` 的角色定位。
- `docs/architecture/03-triangle-agent-architecture.md` 的轮次和门禁设计。
- 前端 PRD 群聊/仲裁交互思路。

## 9. API 协议草案

Antigravity 前端只依赖这些 API，不依赖后端内部文件结构。

### 9.1 创建任务

```http
POST /api/tasks
Content-Type: application/json
```

```json
{
  "type": "manual",
  "username": "alice",
  "title": "节点池",
  "goal": "生成节点池操作手册",
  "instructions": "重点说明扩缩容限制",
  "material_ids": ["file_1", "file_2"]
}
```

返回：

```json
{
  "task_id": "task_20260530_001",
  "status": "created"
}
```

### 9.2 启动任务

```http
POST /api/tasks/{task_id}/run
```

### 9.3 订阅事件

```http
GET /api/tasks/{task_id}/events
Accept: text/event-stream
```

SSE data 示例：

```json
{
  "id": "evt_12",
  "task_id": "task_20260530_001",
  "type": "agent.message.delta",
  "role": "PM",
  "payload": { "text": "## 业务目标\n" },
  "created_at": "2026-05-30T14:00:00+08:00"
}
```

### 9.4 提交仲裁

```http
POST /api/tasks/{task_id}/decisions
```

```json
{
  "decision": "选择方案 B，接受短时间缓存脏数据，但必须加入事后对账。",
  "selected_option": "B"
}
```

### 9.5 查询产物

```http
GET /api/tasks/{task_id}/artifacts
GET /api/artifacts/{artifact_id}
PUT /api/artifacts/{artifact_id}
```

编辑终稿时后端必须备份旧版本，并触发可选 Diff 任务。

### 9.6 文件上传

```http
POST /api/materials
GET /api/materials/{material_id}
DELETE /api/materials/{material_id}
```

上传文件只进入材料库，不直接进入知识库。是否沉淀为可信知识由后续审核流程决定。

## 10. 存储设计

建议把运行态和产物分开：

```text
workspace/
  tasks/
    {task_id}/
      task.json
      events.jsonl
      context.json
      rounds.md
      gate_results.md
  artifacts/
    {username}/
      manual/{module}/...
      prd/{feature}/...
  materials/
    {username}/...
  rules/
    candidates/...
    approved/...
```

如果继续支持独立 Git 文件仓库，应由 `FileService` 封装，业务代码不得直接拼路径。

## 11. LLM 与 Agent 设计

### 11.1 LLMPort

模型调用通过接口隔离：

```python
class LLMPort(Protocol):
    def invoke(self, messages: list[Message], model: str, stream: bool = False) -> LLMResult: ...
```

收益：

- 模型供应商可替换。
- 流式输出可统一转事件。
- 测试时可以用 FakeLLM。

### 11.2 Prompt 结构

继续保留五层 prompt：

```text
## ROLE
## GOAL
## RULES
## LESSONS
## CONTEXT
## OUTPUT
```

但 Prompt 不应散落在编排器里。统一放在 `app/agents/prompts/`，由 `TaskDefinition` 注入任务类型上下文。

### 11.3 Agent 输出结构化

需要驱动流程判断的 Agent 输出，应尽量要求 JSON 或 Markdown + YAML frontmatter。例如 Tech 输出：

```yaml
blocking:
  - id: T1
    issue: Redis 单点风险未说明
    required_change: 补充降级和限流策略
risks:
  - id: T2
    issue: 一致性目标未量化
suggestions: []
```

这样引擎可以稳定判断是否收敛，而不是解析自由文本。

## 12. 前端对接要求

Antigravity 前端需要围绕以下后端能力设计：

1. 任务创建表单：选择 `manual` 或 `prd`。
2. 材料上传区：上传后拿到 `material_id`。
3. 任务直播区：订阅 SSE，展示 PM/Tech/QA/Reviewer 发言。
4. 仲裁面板：收到 `arbitration.requested` 后展示选项并提交裁决。
5. 产物文件树：读取 `artifacts` 列表。
6. Markdown 编辑器：读取和保存产物。
7. 任务状态条：由事件驱动，不读后端日志。

前端不要再依赖 `console.print` 标记，例如 `[__CHAT_MSG_START__|PM]`。这类文本标记应在重构中删除。

## 13. 旧代码处理策略

### 13.1 保留/迁移

| 旧资产 | 处理 |
|---|---|
| `docs/architecture/**` | 保留并按新架构更新 |
| `GBRAIN_ARCHITECTURE.md` | 保留为架构索引 |
| `app/格式.md` | 迁移为 manual 格式规范 |
| `AGENTS.md` | 更新为新工作规则和新架构地图 |
| `AGENT_MAP.md` | 更新为新目录导航 |
| `app/agents/*` prompt | 只迁移有效 prompt 和规则 |
| `app/utils/file_store.py` | 迁移设计思想，重写实现 |
| 前端 UI | 由 Antigravity 判断保留视觉资产或重写 |

### 13.2 删除/重写

| 旧资产 | 处理原因 |
|---|---|
| `app/workflow/orchestrator.py` | 旧手册流程过重，和新任务引擎冲突 |
| `app/workflow/prd_orchestrator.py` | 旧 PRD 流程为单独编排器，需并入通用引擎 |
| `app/server.py` | Mock、真实流程、文件 API 混杂，建议重写 |
| `app/chat.py` | 旧对话入口与新任务模型不一致，建议重写为薄入口或删除 |
| `app/main.py` | 重写为新 `TaskService` 的 CLI 薄入口 |
| `app/static/*.html` | 不再作为后端内置大型页面维护，迁移到 `frontend/` |
| 旧 Memory 注入 | 改为 Diff/Rule 服务，避免隐式污染 Agent 上下文 |

### 13.3 README / CLAUDE / AGENTS 处理

用户允许删除或更新过时文档。建议：

- `README.md`：重写为新项目介绍、运行方式、两类任务、前后端协作方式。
- `AGENTS.md`：重写为 AI 协作规则，明确 Codex 后端、Antigravity 前端分工。
- `CLAUDE.md`：当前是指向 `AGENTS.md` 的软链，可继续保留；如果工具不支持软链，再改为简短跳转说明。
- `AGENT_MAP.md`：重写为新目录导航，避免继续描述旧 orchestrator。

## 14. 分阶段实施计划

### Phase 0：冻结与备份

- 确认当前未跟踪文件是否都要保留。
- 创建重构分支。
- 标记旧架构最后状态。
- 不读取 `.env`，不删除用户材料和输出产物。

### Phase 1：新内核骨架

- 建立 `core/`、`workflows/`、`services/`、`agents/`、`api/`。
- 定义 `TaskDefinition`、`TaskContext`、`Event`、`Artifact`、`WorkflowSpec`、`ToolSpec`。
- 实现 FakeLLM + 单元测试，先不接真实模型。
- 实现事件缓冲和 SSE 基础能力。

### Phase 2：PRD 工作流

- 迁移 PM/Tech/QA/Reviewer 角色 prompt。
- 实现 `prd` TaskDefinition。
- 支持多轮攻防、仲裁暂停/恢复、PRD 产物输出。
- 前端可先用 PRD 流测试事件协议。

### Phase 3：操作手册工作流

- 迁移 `app/格式.md` 和手册红线。
- 实现 `manual` TaskDefinition。
- 支持材料摘要、文档拆分、模块概览、操作文档输出。
- Reviewer 门禁覆盖旧 F1-F17 中仍有效的规则。

### Phase 4：前端联调

- 后端冻结 API/SSE 协议版本。
- Antigravity 对接任务创建、事件直播、仲裁、文件树、编辑器。
- 移除旧日志标记协议。

### Phase 5：清理旧代码与文档

- 删除或迁移旧 `workflow/`、`server.py`、`chat.py`、`static/`。
- 更新 `README.md`、`AGENTS.md`、`AGENT_MAP.md`。
- 保留必要 legacy 说明或迁移清单。
- 跑语法检查和最小端到端任务。

## 15. 验收标准

### 15.1 后端验收

- `manual` 和 `prd` 都能通过同一个 `TaskService` 创建和运行。
- 前端可通过 SSE 收到结构化事件，不解析日志文本。
- 任务可暂停等待用户裁决，并在提交裁决后恢复。
- 任务产物可列出、读取、保存和备份。
- 后续新增任务类型不需要修改 `WorkflowEngine` 主流程。
- 单元测试覆盖任务状态流转、仲裁恢复、Artifact 写入、Tool 权限拒绝、FakeLLM 工作流。

### 15.2 前后端联调验收

- 前端可创建 `manual` 和 `prd` 两类任务。
- 直播区能区分 PM、Tech、QA、Reviewer。
- 仲裁事件出现时 UI 能暂停任务并提交裁决。
- 产物文件树能展示最终 Markdown。
- 编辑保存后后端有备份记录。

### 15.3 清理验收

- README、AGENTS、AGENT_MAP 不再描述旧 Orchestrator 作为主架构。
- 旧 Mock PRD 逻辑删除。
- 旧大型静态 HTML 不再由后端维护。
- 旧流程文件不再被新入口引用。

## 16. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 一次删除过多导致能力丢失 | 手册规则或 PRD 角色经验丢失 | 先迁移 prompt 和格式规则，再删旧代码 |
| 前后端协议频繁变化 | Antigravity 联调成本高 | 先冻结 API/SSE 草案，变更走版本说明 |
| Agent 输出不可解析 | 引擎无法判断收敛 | 关键输出要求结构化 JSON/YAML |
| GBrain 未就绪 | 知识检索能力缺失 | `KnowledgePort` 先接本地文件/空实现，后续替换 |
| 手册和 PRD 差异过大 | 通用引擎被迫膨胀 | 引擎只管生命周期，差异放进 `TaskDefinition` 策略 |
| 旧前端依赖日志标记 | 新事件协议对接困难 | 明确废弃日志标记，提供 SSE 示例 fixture |

## 17. 开发约定

- 后端新增代码默认写类型注解。
- 编排逻辑不得直接拼输出路径，必须走 `FileService`。
- Agent 不直接读写文件，只返回结构化结果；需要外部能力时只能请求白名单 Tool。
- 前端不直接调用模型，不直接写知识库。
- Prompt 修改只改 prompt 模块，不改任务引擎。
- 新功能必须先新增 `TaskDefinition`，除非生命周期能力确实缺失。
- 新 Tool 必须先定义 `ToolSpec`、权限策略、事件输出和失败语义，再允许 Agent 使用。
- 不读取 `.env`；配置示例只看 `.env.example`。
- 不默认读取 `workspace/outputs/`、`workspace/inputs/temp/`、完整知识库和样例库。

## 18. 推荐下一步

1. Codex 根据本文档创建新后端骨架和 FakeLLM 测试。
2. Antigravity 根据第 9、12 节设计新版前端接口和页面状态。
3. 双方先用 `prd` 工作流联调，因为它最能验证 PM-Agent 轮次、仲裁和事件协议。
4. `prd` 跑通后再迁移 `manual`，避免两个复杂工作流同时重构。
5. 在真实模型接入前，先用 FakeLLM + FakeTool 跑通 Workflow 暂停、恢复、Tool 审计和产物写入。
