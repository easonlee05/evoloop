# EvoLoop 前端交接文档

> 交接方：Claude Sonnet 4.6
> 接收方：Codex
> 日期：2026-05-31
> 任务：前后端联调

---

## 一、项目概览

EvoLoop 是一个多 Agent 协同的 AI SaaS 平台，前端已完成高保真 UI 重构，风格参考 Sana AI（极简、纯白、无阴影）。

**技术栈**：React 18 + Vite 6 + React Router v6 + lucide-react，纯 CSS，无 UI 组件库。

**启动方式**：
```bash
cd frontend
npm install
npm run dev   # 默认端口 4000
```

---

## 二、路由结构

| 路由 | 页面文件 | 说明 |
|------|----------|------|
| `/` | `pages/LandingPage/LandingPage.jsx` | 首页，输入任务后跳转工作台 |
| `/tasks` | `pages/Tasks/index.jsx` | 任务大厅，点击行进工作台 |
| `/workspace/:id` | `pages/Workspace/index.jsx` | 工作台，Agent 直播 + 文档编辑 |
| `/knowledge-base` | `pages/KnowledgeBase/index.jsx` | 知识库，支持新建 |
| `/rule-audit` | `pages/RuleAudit/index.jsx` | 法则审核，批准/驳回操作 |
| `/recycle-bin` | `pages/RecycleBin/index.jsx` | 回收站，恢复/永久删除 |

所有页面共用 `components/layout/MainLayout.jsx`（Sidebar + 内容区，无顶部 Header）。

---

## 三、Mock 数据位置（需替换为真实 API）

> Codex 对接更新（2026-05-31）：以下页面已接入后端兼容 API，并保留原 mock 作为后端不可用时的视觉兜底；未改动 CSS/设计 token。

| 文件 | Mock 变量 | 替换为 |
|------|-----------|--------|
| `pages/Workspace/index.jsx` | `SCRIPT`（Agent 剧本）、`DOC`（文档内容） | SSE/WebSocket 实时流 |
| `pages/Tasks/index.jsx` | `tasks` 数组 | `GET /api/tasks` |
| `pages/KnowledgeBase/index.jsx` | `initItems` 数组 | `GET /api/knowledge` |
| `pages/RuleAudit/index.jsx` | `rules`、`approvedRules`、`rejectedRules` | `GET /api/rules` |
| `pages/RecycleBin/index.jsx` | `items` 数组 | `GET /api/recycle` |
| `components/layout/Sidebar.jsx` | `recentChats`、`yesterdayChats` | `GET /api/conversations/recent` |

后端 contract 以 `docs/refactor/api-contract.md` 为准。默认前端 API Base 为 `http://127.0.0.1:8000`，可用 `VITE_API_BASE` 覆盖。

---

## 四、各页面联调说明

### 4.1 LandingPage（首页）

**当前行为**：输入内容 → 点发送 → 1.2s 动画 → 硬跳转 `/workspace/new`

**需要改成**：
1. 调用 `POST /api/tasks` 创建任务，body 为 `{ prompt: string }`
2. 拿到返回的 `taskId`
3. 跳转 `/workspace/:taskId`

```jsx
// 当前代码位置：LandingPage.jsx handleSend()
setTimeout(() => {
  navigate('/workspace/new');  // ← 替换这里
}, 1200);
```

---

### 4.2 Workspace（工作台，最核心）

**Agent 消息结构**（当前 mock 在 `SCRIPT` 常量）：
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

**实时流接入点**：替换 `useEffect` 里的 `playNext()` 逻辑，改为监听 SSE 或 WebSocket：
```jsx
// pages/Workspace/index.jsx，useEffect 第二个（启动剧本）
useEffect(() => {
  playNext(0);  // ← 替换为 connectStream(taskId)
  ...
}, []);
```

**打断接口**：`handleInterrupt()` 函数里加 `POST /api/tasks/:id/interrupt`

**文档内容**：`DOC` 常量替换为 `GET /api/tasks/:id/document`，保存时调用 `PUT /api/tasks/:id/document`

---

### 4.3 任务大厅

- 列表数据：`GET /api/tasks`，返回数组，字段对应 `tasks` 数组结构
- 状态字段枚举：`running | review | pending | done`
- 点击行跳转 `/workspace/:id`（已实现）

---

### 4.4 知识库

- 列表：`GET /api/knowledge`
- 新建：`POST /api/knowledge`，支持 multipart（含文件上传）
- 类型枚举：`doc | rule | template`

---

### 4.5 法则审核

- 列表：`GET /api/rules?status=pending|approved|rejected`
- 批准：`POST /api/rules/:id/approve`
- 修改后入库：`POST /api/rules/:id/approve`，body 带修改内容
- 驳回：`POST /api/rules/:id/reject`
- `confidence` 字段由后端 Diff Agent 提供（0-100）

---

### 4.6 回收站

- 列表：`GET /api/recycle`
- 恢复：`POST /api/recycle/:id/restore`
- 永久删除：`DELETE /api/recycle/:id`

---

## 五、设计 Token

全部在 `src/index.css` 的 `:root` 里，修改颜色/间距直接改变量：

```css
--bg-app: #ffffff;          /* 页面背景 */
--text-primary: #0a0a0a;    /* 主文字 */
--text-secondary: #6b6b6b;  /* 次要文字 */
--text-tertiary: #a0a0a0;   /* 辅助文字 */
--border: #e8e8e8;          /* 边框 */
--accent: #5c5cf0;          /* 品牌色（暂未大量使用，保留备用）*/
```

---

## 六、已知待完善项

| 问题 | 位置 | 优先级 |
|------|------|--------|
| Sidebar 最近对话为静态 mock | `Sidebar.jsx` | 高 |
| 工作台文档编辑器为纯 textarea，无富文本 | `Workspace/index.jsx` | 中 |
| 知识库卡片点击无详情页 | `KnowledgeBase/index.jsx` | 中 |
| 法则审核"修改后入库"无编辑弹窗 | `RuleAudit/index.jsx` | 中 |
| 任务大厅无分页 | `Tasks/index.jsx` | 低 |
