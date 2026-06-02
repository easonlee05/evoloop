# 前端架构

当前前端的核心是工作台页面 `frontend/src/pages/Workspace/index.jsx`。它负责展示任务会话、文档编辑、知识提示和任务动作，不负责模型推理本身。

## 页面组成

| 区域 | 作用 |
|---|---|
| 左侧任务栏 | 展示最近任务、知识卡片、规则卡片和回收站入口 |
| 中间会话区 | 展示 Agent 消息、状态、仲裁提示和 toast |
| 右侧文档区 | 展示和编辑当前 Markdown 文档 |
| 输入区 | 提交消息、仲裁意见和带引用的用户输入 |

## 当前交互规则

- 进入任务后不会自动打开文档区。
- 打开已存在任务、已中断任务或未完成任务时，不会自动执行。
- 文档入口固定在右上角动作区，通过按钮显式打开或查看文档。
- 任务继续运行由用户显式触发，不和“打开任务”绑定。
- 知识提示采用 toast 形式显示，不占用主体内容宽度。

## 会话区与引用交互

当前引用能力同时支持会话区和文档区的已选文本：

- 选中任意会话消息内容，可生成引用项。
- 选中文档编辑区内容，也可生成引用项。
- 多次选择会聚合成一个引用胶囊，而不是生成多条重复消息。
- 悬浮文案展示来源标签和摘要文本。
- 单条引用最多展示 150 字；引用越多，每条分配的展示长度越短。
- 悬浮层没有滚动条，空间不足时直接使用省略号。

核心逻辑位于：

- `frontend/src/pages/Workspace/quoteSelection.js`
- `frontend/src/pages/Workspace/workspaceSession.js`
- `frontend/src/pages/Workspace/workspaceActions.js`

## 文档区

文档区基于 TipTap 和 Markdown 转换能力实现，当前支持：

- 读取任务最新 Markdown 文档
- 编辑并保存当前文档
- 保存前自动备份旧 artifact 版本
- 在阅读和编辑之间切换
- 从文档选中文本直接加入引用胶囊

## 前端与后端协作

前端只依赖结构化 API：

- `GET /api/tasks`
- `POST /api/tasks`
- `POST /api/tasks/{task_id}/run`
- `GET /api/tasks/{task_id}/events`
- `GET /api/tasks/{task_id}/document`
- `PUT /api/tasks/{task_id}/document`
- `POST /api/tasks/{task_id}/decisions`
- `GET /api/conversations/recent`

请求封装位于 `frontend/src/api.js`。前端不解析控制台输出，也不依赖后端日志标记。

## 当前约束

- 页面状态以 API 返回和 SSE 事件为准。
- 文档打开、任务运行和仲裁提交必须显式触发。
- 任何知识提示、规则状态或降级提示都不能泄露私有材料原文或本地路径。
