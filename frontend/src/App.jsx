/**
 * @file App.jsx
 * @description 应用的根组件。配置客户端路由（react-router-dom），并根据不同的 URL 路径挂载不同的页面。
 * 大部分页面都会使用 MainLayout 进行包裹，以提供一致的头部导航和左侧边栏。
 */

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import LandingPage from './pages/LandingPage/LandingPage';
import Tasks from './pages/Tasks/index';
import Workspace from './pages/Workspace/index';
import KnowledgeBase from './pages/KnowledgeBase/index';
import RuleAudit from './pages/RuleAudit/index';
import RecycleBin from './pages/RecycleBin/index';

/**
 * 临时占位组件，用于展示尚未完全实现的页面/功能。
 * @component
 * @param {Object} props
 * @param {string} props.name - 正在开发的页面名称
 */
function Placeholder({ name }) {
  return <div style={{ padding: 40, color: '#a0a0a0', fontSize: 14 }}>正在开发：{name}</div>;
}

/**
 * 页面嵌套包裹辅助组件。
 * 将具体页面用 `MainLayout` 包裹起来，并统一定义页面标题 (title) 和面包屑导航 (breadcrumbs)。
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 需要包裹的子页面组件
 * @param {string} props.title - 页面标题
 * @param {Array<string>} [props.crumbs] - 面包屑导航项数组
 */
function W({ children, title, crumbs }) {
  return <MainLayout title={title} breadcrumbs={crumbs}>{children}</MainLayout>;
}

/**
 * 全局 App 路由导航控制中心。
 * @component
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 首页/欢迎页 */}
        <Route path="/" element={<W title="首页"><LandingPage /></W>} />
        {/* 任务大厅：展示当前正在运行或已规划的任务列表 */}
        <Route path="/tasks" element={<W title="任务大厅"><Tasks /></W>} />
        {/* 任务工作台：根据任务 ID 进行深度操作的工作空间，使用 MainLayout 但隐藏通用 Header 而是采用工作台专属头部 */}
        <Route path="/workspace/:id" element={<MainLayout noHeader><Workspace /></MainLayout>} />
        {/* 知识库：数字资产、参考资料管理 */}
        <Route path="/knowledge-base" element={<W title="知识库"><KnowledgeBase /></W>} />
        {/* 法则审核：AI 规则、安全策略的审计页面 */}
        <Route path="/rule-audit" element={<W title="法则审核"><RuleAudit /></W>} />
        {/* 回收站：用于存放已删除或下线的任务包 */}
        <Route path="/recycle-bin" element={<W title="回收站"><RecycleBin /></W>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

