# 局部项目内存 (MEMORY.md 指针索引)

> **[系统锁定]** 这是三级持久化内存架构中的 L2 索引。
> 本文件应严格限制在 200 行以内。当项目复杂度上升时，将具体内容拆分至子目录（如 `docs/memory/`）并在下方保留链接指针。

## 1. 核心架构与契约指针
- **3.0 全局架构**: [00-global-architecture.md](docs/evoloop-3.0/architecture/00-global-architecture.md)
- **技术演进路线**: [00-evolution-roadmap.md](docs/evoloop-3.0/technical/00-evolution-roadmap.md)
- **并行开发规范**: [01-parallel-development-boundaries.md](docs/evoloop-3.0/technical/01-parallel-development-boundaries.md)

## 2. 工具与接口准则
- 所有的受控动作（如读取、写入、查询）均需经由白名单 ToolPolicy。
- 工具输出需遵循 Microcompact 原则，严禁将全量日志直接灌入 LLM Prompt。

## 3. 已确立的核心实体
- **WorkItem**: 当前系统唯一任务载体。
- **machine_spec**: 唯一真实的业务契约与意图源，后续 PRD 与 Agent Package 均由其投影。
