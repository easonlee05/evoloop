import React, { useState, useRef } from 'react';
import { Search, Plus, FileText, FolderOpen, MoreHorizontal, Clock, Download, Trash2, Grid, List } from 'lucide-react';
import './file-center.css';
import { apiUpload } from '../../api';

const tabs = ['全部', '文档', '图片', '其他'];

const files = [
  { id: 1, name: '产品需求文档 v2.0.md', type: 'doc', size: '48 KB', updated: '10 分钟前', author: 'PM Agent', task: 'T-0421' },
  { id: 2, name: 'EvoLoop 架构设计文档.md', type: 'doc', size: '92 KB', updated: '2 小时前', author: 'Tech Agent', task: 'T-0420' },
  { id: 3, name: '用户增长策略分析报告.md', type: 'doc', size: '64 KB', updated: '昨天', author: 'Intern', task: 'T-0420' },
  { id: 4, name: '竞品功能对比分析.md', type: 'doc', size: '36 KB', updated: '昨天', author: 'Expert', task: 'T-0418' },
  { id: 5, name: 'API 网关压测报告.md', type: 'doc', size: '28 KB', updated: '2 天前', author: 'QA Agent', task: 'T-0416' },
  { id: 6, name: '系统架构图 v1.png', type: 'img', size: '1.2 MB', updated: '3 天前', author: 'Tech Agent', task: 'T-0416' },
  { id: 7, name: '法则库季度审查报告.md', type: 'doc', size: '52 KB', updated: '5 天前', author: 'Reviewer', task: 'T-0417' },
  { id: 8, name: '新用户引导流程图.png', type: 'img', size: '860 KB', updated: '1 周前', author: 'PM Agent', task: 'T-0415' },
];

const typeMap = { doc: '文档', img: '图片' };
const typeIcon = { doc: <FileText size={15} />, img: <FolderOpen size={15} /> };
const typeColor = { doc: '#2563eb', img: '#7c3aed' };

export default function FileCenter() {
  const [tab, setTab] = useState('全部');
  const [query, setQuery] = useState('');
  const [view, setView] = useState('list');
  const fileInputRef = useRef(null);

  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = '';
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
    }
  };

  const filtered = files.filter(f => {
    const matchTab = tab === '全部' || typeMap[f.type] === tab;
    const matchQuery = !query || f.name.includes(query);
    return matchTab && matchQuery;
  });

  return (
    <div className="file-page">
      <div className="file-top">
        <div>
          <h1 className="page-title">文件中心</h1>
          <p className="page-sub">任务产出的所有文档与附件</p>
        </div>
        <button className="btn-primary-sm" onClick={() => fileInputRef.current?.click()}>
          <Plus size={13} />上传文件
        </button>
        <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleUpload} />
      </div>

      <div className="file-toolbar">
        <div className="file-tabs">
          {tabs.map(t => (
            <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
        <div className="file-toolbar-right">
          <div className="file-search">
            <Search size={13} className="search-icon" />
            <input className="search-input" placeholder="搜索文件…" value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <div className="view-toggle">
            <button className={`view-btn${view === 'list' ? ' active' : ''}`} onClick={() => setView('list')}><List size={14} /></button>
            <button className={`view-btn${view === 'grid' ? ' active' : ''}`} onClick={() => setView('grid')}><Grid size={14} /></button>
          </div>
        </div>
      </div>

      {view === 'list' ? (
        <div className="file-table">
          <div className="file-table-head">
            <div className="fcol-name">文件名</div>
            <div className="fcol-task">来源任务</div>
            <div className="fcol-author">创建者</div>
            <div className="fcol-size">大小</div>
            <div className="fcol-time">更新时间</div>
            <div className="fcol-action" />
          </div>
          {filtered.map(f => (
            <div key={f.id} className="file-row">
              <div className="fcol-name">
                <span className="file-icon" style={{ color: typeColor[f.type] }}>{typeIcon[f.type]}</span>
                <span className="file-name">{f.name}</span>
              </div>
              <div className="fcol-task file-task">{f.task}</div>
              <div className="fcol-author file-meta">{f.author}</div>
              <div className="fcol-size file-meta">{f.size}</div>
              <div className="fcol-time file-meta">{f.updated}</div>
              <div className="fcol-action">
                <button className="row-action"><Download size={13} /></button>
                <button className="row-action"><MoreHorizontal size={13} /></button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="file-grid">
          {filtered.map(f => (
            <div key={f.id} className="file-card">
              <div className="file-card-icon" style={{ color: typeColor[f.type], background: typeColor[f.type] + '10' }}>
                {typeIcon[f.type]}
              </div>
              <div className="file-card-name">{f.name}</div>
              <div className="file-card-meta">{f.size} · {f.updated}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
