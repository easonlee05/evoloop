import React, { useEffect, useState } from 'react';
import { Plus, MoreHorizontal, Filter } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../../api';
import './tasks.css';

const tasks = [
  { id: 'T-0421', title: '产品需求文档 v2.0 评审', status: 'running', agent: 'PM + Tech + QA', priority: 'high', updated: '10 分钟前' },
  { id: 'T-0420', title: '用户增长策略分析报告', status: 'review', agent: 'Intern + Reviewer', priority: 'medium', updated: '1 小时前' },
  { id: 'T-0419', title: '云原生架构迁移方案', status: 'pending', agent: '待分配', priority: 'high', updated: '2 小时前' },
  { id: 'T-0418', title: '竞品功能对比分析', status: 'done', agent: 'Expert', priority: 'low', updated: '昨天' },
  { id: 'T-0417', title: '法则库季度审查', status: 'done', agent: 'Reviewer', priority: 'medium', updated: '昨天' },
  { id: 'T-0416', title: 'API 网关性能压测报告', status: 'done', agent: 'Tech + QA', priority: 'high', updated: '2 天前' },
  { id: 'T-0415', title: '新用户引导流程优化', status: 'done', agent: 'PM + Intern', priority: 'low', updated: '3 天前' },
];

const statusMap = {
  running: { label: '运行中', color: '#2563eb' },
  review:  { label: '审查中', color: '#d97706' },
  pending: { label: '待启动', color: '#a0a0a0' },
  done:    { label: '已完成', color: '#16a34a' },
};

const priorityMap = { high: '高', medium: '中', low: '低' };
const priorityColor = { high: '#dc2626', medium: '#d97706', low: '#a0a0a0' };

const tabs = ['全部', '运行中', '审查中', '待启动', '已完成'];

export default function Tasks() {
  const [tab, setTab] = useState('全部');
  const [items, setItems] = useState(tasks);
  const navigate = useNavigate();
  const list = tab === '全部' ? items : items.filter(t => statusMap[t.status]?.label === tab);

  useEffect(() => {
    apiGet('/api/tasks', { tasks }).then(data => setItems(data.tasks || tasks));
  }, []);

  return (
    <div className="tasks-page">
      <div className="page-top">
        <h1 className="page-title">任务大厅</h1>
        <button className="btn-primary-sm" onClick={() => navigate('/')}><Plus size={13} />新建任务</button>
      </div>

      <div className="tab-bar">
        {tabs.map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
        <div className="tab-spacer" />
        <button className="btn-ghost-sm"><Filter size={13} />筛选</button>
      </div>

      <div className="table">
        <div className="table-head">
          <div className="col-name">任务名称</div>
          <div className="col-status">状态</div>
          <div className="col-agent">执行 Agent</div>
          <div className="col-pri">优先级</div>
          <div className="col-time">更新</div>
          <div className="col-more" />
        </div>
        {list.map((t, i) => {
          const s = statusMap[t.status] || statusMap.pending;
          return (
            <div key={i} className="table-row" onClick={() => navigate(`/workspace/${t.id}`)}>
              <div className="col-name">{t.title}</div>
              <div className="col-status">
                <span className="s-dot" style={{ background: s.color }} />
                {s.label}
              </div>
              <div className="col-agent">{t.agent}</div>
              <div className="col-pri" style={{ color: priorityColor[t.priority] }}>{priorityMap[t.priority]}</div>
              <div className="col-time">{t.updated}</div>
              <div className="col-more">
                <button className="more-btn"><MoreHorizontal size={14} /></button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
