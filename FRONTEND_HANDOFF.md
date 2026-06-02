# EvoLoop 前端与后端交互规范

EvoLoop 是一个多 Agent 协同的 AI SaaS 平台，前端采用 Sana AI 风格重构版 UI（极简、纯白、无阴影）。

**技术栈**：React 18 + Vite 6 + React Router v6 + lucide-react，纯 CSS，无 UI 组件库。

---

## 一、路由结构

| 路由 | 页面文件 | 说明 |
|------|----------|------|
| `/` | `pages/LandingPage/LandingPage.jsx` | 首页，输入任务后跳转工作台 |
| `/tasks` | `pages/Tasks/index.jsx` | 任务大厅，点击进入工作台 |
| `/workspace/:id` | `pages/Workspace/index.jsx` | 工作台，Agent 直播与文档编辑区 |
| `/knowledge-base` | `pages/KnowledgeBase/index.jsx` | 知识库，支持上传材料 |
| `/rule-audit` | `pages/RuleAudit/index.jsx` | 法则审核，执行批准与驳回 |
| `/recycle-bin` | `pages/RecycleBin/index.jsx` | 回收站，支持恢复与删除 |

所有页面共用 `components/layout/MainLayout.jsx`（Sidebar + 内容区，无顶部 Header）。

---

## 二、数据流与 API 对接规范

工作台页面已完全与后端 API 进行了对接。后端接口契约详见 [api-contract.md](file:///Users/apple/Desktop/evoloop/docs/refactor/api-contract.md)。

| 模块 | 数据来源 | 接口类型 |
|------|-----------|--------|
| `Workspace`（会话与文档） | SSE 实时流 / JSON | `GET /api/tasks/{id}/events` 与 `GET /api/tasks/{id}/document` |
| `Tasks`（任务大厅） | 任务数组 | `GET /api/tasks` |
| `KnowledgeBase`（知识库） | 知识项列表 | `GET /api/knowledge` |
| `RuleAudit`（法则审核） | 规则卡片 | `GET /api/rules` |
| `RecycleBin`（回收站） | 回收站数据 | `GET /api/recycle` |
| `Sidebar`（最近任务） | 活跃会话 | `GET /api/conversations/recent` |

前端 API Base 默认为 `http://127.0.0.1:8000`，可通过 `VITE_API_BASE` 覆盖。

---

## 三、数据交互说明

### 3.1 LandingPage（首页）

1. 调用 `POST /api/tasks` 创建任务，请求参数为 `{ prompt: string }`。
2. 后端推断任务类型并返回 `taskId`。
3. 导航至 `/workspace/:taskId` 进入工作台。

---

### 3.2 Workspace（工作台）

**Agent 消息结构**：
```js
{
  agent: 'PM Agent',       // 显示名
  role: '主导中',           // 状态标签
  avatar: 'PM',            // 头像文字
  color: '#7c3aed',        // 主题色
  content: '...',          // 消息正文
  highlights: {            // 可选，高亮卡片
    label: '关注要点',
    color: '#7c3aed',
    items: ['...', '...'],
  },
  isFinal: false,          // true = 讨论结束，触发完成卡片
}
```

- **实时流接入**：前端通过 EventSource 订阅 `/api/tasks/{task_id}/events` 获取实时任务事件与流式消息。
- **打断任务**：调用 `POST /api/tasks/{task_id}/interrupt` 中断任务执行。
- **文档管理**：通过 `GET /api/tasks/{task_id}/document` 获取 Markdown 文档，通过 `PUT /api/tasks/{task_id}/document` 保存修改。

---

### 3.3 任务大厅

- 列表数据：`GET /api/tasks`。
- 状态类型：`running | review | pending | done`。
- 点击特定任务行直接进入工作台 `/workspace/:id`。

---

### 3.4 知识库

- 获取列表：`GET /api/knowledge`。
- 上传知识：`POST /api/knowledge`（支持 multipart 格式上传材料）。

---

### 3.5 法则审核

- 规则列表：`GET /api/rules?status=pending|approved|rejected`。
- 批准/编辑入库：`POST /api/rules/{id}/approve`。
- 驳回：`POST /api/rules/{id}/reject`。
- 置信度字段：`confidence` 范围为 0-100。

---

### 3.6 回收站

- 列表：`GET /api/recycle`。
- 恢复：`POST /api/recycle/{id}/restore`。
- 永久删除：`DELETE /api/recycle/{id}`。

---

## 四、设计 Token

全部在 `src/index.css` 的 `:root` 里，修改颜色/间距直接改变量：

```css
--bg-app: #ffffff;          /* 页面背景 */
--text-primary: #0a0a0a;    /* 主文字 */
--text-secondary: #6b6b6b;  /* 次要文字 */
--text-tertiary: #a0a0a0;   /* 辅助文字 */
--border: #e8e8e8;          /* 边框 */
--accent: #5c5cf0;          /* 品牌色 */
```
