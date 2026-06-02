import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import LandingPage from './pages/LandingPage/LandingPage';
import Tasks from './pages/Tasks/index';
import Workspace from './pages/Workspace/index';
import KnowledgeBase from './pages/KnowledgeBase/index';
import RuleAudit from './pages/RuleAudit/index';
import RecycleBin from './pages/RecycleBin/index';

function Placeholder({ name }) {
  return <div style={{ padding: 40, color: '#a0a0a0', fontSize: 14 }}>正在开发：{name}</div>;
}

function W({ children, title, crumbs }) {
  return <MainLayout title={title} breadcrumbs={crumbs}>{children}</MainLayout>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<W title="首页"><LandingPage /></W>} />
        <Route path="/tasks" element={<W title="任务大厅"><Tasks /></W>} />
        <Route path="/workspace/:id" element={<MainLayout noHeader><Workspace /></MainLayout>} />
        <Route path="/knowledge-base" element={<W title="知识库"><KnowledgeBase /></W>} />
        <Route path="/rule-audit" element={<W title="法则审核"><RuleAudit /></W>} />
        <Route path="/recycle-bin" element={<W title="回收站"><RecycleBin /></W>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
