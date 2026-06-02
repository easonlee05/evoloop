# PM-Agent 核心架构

EvoLoop 是以 PM-Agent 为核心的双产品线平台，当前支持两类任务：`manual`（操作手册编写）和 `prd`（PRD 编写）。

## 核心能力与工作模式

PM-Agent 基于一套通用的任务执行引擎进行调度。当用户提供输入后，Agent 通过以下方式完成任务：

1. **共享上下文**：在同一个 `TaskContext` 上运行，确保所有步骤和分析基于相同的事实。
2. **多角色协作**：在工作流中扮演 PM、Tech、QA、Reviewer、Writer 等虚拟角色，并按步骤编排协同完成文档。
3. **安全沙箱控制**：Agent 不直接读写文件、不直接访问网络，所有外部能力均通过 `ToolService` 的白名单（ToolPolicy）执行。
4. **人类裁决（Human-in-the-loop）**：在遇到业务取舍、冲突或重要 gate 失败时，Agent 自动暂停并发出裁决请求，用户反馈后从断点继续运行。
5. **结构化事件驱动**：执行过程中的流式消息、步骤状态及门禁结果，均通过结构化事件推送至前端。

## 任务执行流程

### manual（操作手册编写）
`ingest_materials` -> `build_context` -> `retrieve_knowledge` -> `PM提纲` -> `Tech/QA并行校验` -> `Reviewer门禁` -> `Writer生成文档` -> `Reviewer文档门禁` -> `写入Artifact`。

### prd（PRD 编写）
`build_context` -> `retrieve_knowledge` -> `PM草案` -> `Tech/QA挑战` -> `PM初稿` -> `Tech/QA二审` -> `收敛门禁` -> `用户仲裁(需要时)` -> `Reviewer门禁` -> `Writer产出PRD` -> `写入Artifact`。

## 运行与验证

### 启动服务
后端：
```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

前端：
```bash
npm --prefix frontend run dev
```

### 验证命令
```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
npm --prefix frontend run build
```
