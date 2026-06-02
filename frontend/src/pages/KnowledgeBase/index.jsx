import React, { useEffect, useState, useRef } from 'react';
import { Search, Plus, FileText, Shield, Layout, MoreHorizontal, Clock, X, Upload, File } from 'lucide-react';
import { apiGet, apiPost, apiUpload } from '../../api';
import './knowledge-base.css';

const tabs = ['全部', '文档', '规则', '模板'];

const typeConfig = {
  doc:      { label: '文档',  icon: <FileText size={16} />, color: '#2563eb' },
  rule:     { label: '规则',  icon: <Shield size={16} />,   color: '#7c3aed' },
  template: { label: '模板',  icon: <Layout size={16} />,   color: '#d97706' },
};

const initItems = [
  { id: 1, type: 'doc',      title: 'EvoLoop 平台架构设计文档',   desc: '描述平台整体架构、核心模块划分及各层职责，包含进化引擎、规则 DSL、观测反馈闭环三层设计。', tags: ['架构', '核心文档'], updated: '2 小时前', author: 'Tech Agent' },
  { id: 2, type: 'rule',     title: '进化策略安全护栏规则集',     desc: '定义进化过程中的风险阈值、自动回滚触发条件及异常检测规则，确保系统稳定性。',             tags: ['规则', '安全'],   updated: '昨天',    author: 'QA Agent' },
  { id: 3, type: 'template', title: 'PRD 标准模板 v2.0',          desc: '产品需求文档标准模板，包含概述、目标、成功指标、用户角色、功能需求、非功能需求六大模块。', tags: ['模板', 'PRD'],    updated: '3 天前',  author: 'PM Agent' },
  { id: 4, type: 'doc',      title: 'Agent 协作流程规范',         desc: '规定 PM、Tech、QA 三方 Agent 的协作顺序、发言规则、死锁处理机制及人工介入触发条件。',     tags: ['流程', '规范'],   updated: '3 天前',  author: 'PM Agent' },
  { id: 5, type: 'rule',     title: '知识入库审核规则',           desc: '定义候选法则从 Diff 提炼到正式入库的完整审核流程，包含批准、修改、驳回及范围限定四种处理方式。', tags: ['规则', '审核'], updated: '5 天前',  author: 'Reviewer' },
  { id: 6, type: 'template', title: '技术方案评审模板',           desc: '用于架构评审的标准模板，涵盖方案背景、技术选型、风险评估、回滚方案四个核心章节。',         tags: ['模板', '技术'],   updated: '1 周前',  author: 'Tech Agent' },
];

const typeMap = { doc: '文档', rule: '规则', template: '模板' };

export default function KnowledgeBase() {
  const [tab, setTab]       = useState('全部');
  const [query, setQuery]   = useState('');
  const [items, setItems]   = useState(initItems);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    apiGet('/api/knowledge', { items: initItems }).then(data => setItems(data.items || initItems));
  }, []);

  const filtered = items.filter(item => {
    const matchTab   = tab === '全部' || typeMap[item.type] === tab;
    const matchQuery = !query || item.title.includes(query) || item.desc.includes(query);
    return matchTab && matchQuery;
  });

  const handleCreate = async (newItem) => {
    const created = await apiPost('/api/knowledge', newItem, { ...newItem, id: Date.now(), updated: '刚刚', author: 'Eason' });
    setItems(prev => [created, ...prev]);
    setShowModal(false);
  };

  return (
    <div className="kb-page">
      <div className="kb-top">
        <div>
          <h1 className="page-title">知识库</h1>
          <p className="page-sub">团队共享的文档、规则与模板</p>
        </div>
        <button className="btn-primary-sm" onClick={() => setShowModal(true)}>
          <Plus size={13} />新建
        </button>
      </div>

      <div className="kb-toolbar">
        <div className="kb-search">
          <Search size={13} className="kb-search-icon" />
          <input className="kb-search-input" placeholder="搜索知识库…" value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        <div className="kb-tabs">
          {tabs.map(t => (
            <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
      </div>

      <div className="kb-grid">
        {filtered.map(item => {
          const tc = typeConfig[item.type];
          return (
            <div key={item.id} className="kb-card">
              <div className="kb-card-header">
                <div className="kb-card-icon" style={{ background: tc.color + '12', color: tc.color }}>{tc.icon}</div>
                <button className="more-btn"><MoreHorizontal size={14} /></button>
              </div>
              <div className="kb-card-title">{item.title}</div>
              <div className="kb-card-desc">{item.desc}</div>
              <div className="kb-card-footer">
                <div className="kb-tags">
                  {item.tags.map((tag, i) => <span key={i} className="kb-tag">{tag}</span>)}
                </div>
                <div className="kb-meta"><Clock size={11} /><span>{item.updated}</span></div>
              </div>
            </div>
          );
        })}
      </div>

      {showModal && <NewItemModal onClose={() => setShowModal(false)} onCreate={handleCreate} />}
    </div>
  );
}

function NewItemModal({ onClose, onCreate }) {
  const [type, setType]     = useState('doc');
  const [title, setTitle]   = useState('');
  const [desc, setDesc]     = useState('');
  const [tags, setTags]     = useState('');
  const [files, setFiles]   = useState([]);
  const fileInputRef        = useRef(null);

  const handleFileChange = async (e) => {
    const picked = Array.from(e.target.files);
    setFiles(prev => [...prev, ...picked]);
    e.target.value = '';
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
    }
  };

  const removeFile = (idx) => setFiles(prev => prev.filter((_, i) => i !== idx));

  const handleSubmit = () => {
    if (!title.trim()) return;
    onCreate({
      type,
      title: title.trim(),
      desc: desc.trim(),
      tags: tags.split(/[,，]/).map(t => t.trim()).filter(Boolean),
      files,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">新建知识条目</span>
          <button className="modal-close" onClick={onClose}><X size={15} /></button>
        </div>

        <div className="modal-body">
          <div className="form-field">
            <label className="form-label">类型</label>
            <div className="type-selector">
              {Object.entries(typeConfig).map(([key, cfg]) => (
                <button
                  key={key}
                  className={`type-btn${type === key ? ' active' : ''}`}
                  onClick={() => setType(key)}
                >
                  <span style={{ color: cfg.color }}>{cfg.icon}</span>
                  {cfg.label}
                </button>
              ))}
            </div>
          </div>

          <div className="form-field">
            <label className="form-label">标题</label>
            <input
              className="form-input"
              placeholder="输入标题…"
              value={title}
              onChange={e => setTitle(e.target.value)}
              autoFocus
            />
          </div>

          <div className="form-field">
            <label className="form-label">描述</label>
            <textarea
              className="form-textarea"
              placeholder="简要描述这条知识的内容和用途…"
              value={desc}
              onChange={e => setDesc(e.target.value)}
              rows={3}
            />
          </div>

          <div className="form-field">
            <label className="form-label">标签 <span className="form-hint">用逗号分隔</span></label>
            <input
              className="form-input"
              placeholder="如：架构, 规范, 核心文档"
              value={tags}
              onChange={e => setTags(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label">上传文件 <span className="form-hint">可选</span></label>
            <div
              className="upload-zone"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={e => {
                e.preventDefault();
                setFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]);
              }}
            >
              <Upload size={16} className="upload-icon" />
              <span className="upload-text">点击上传或拖拽文件到此处</span>
              <span className="upload-hint">支持 PDF、Word、Markdown、图片等格式</span>
            </div>
            <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleFileChange} />
            {files.length > 0 && (
              <div className="file-list">
                {files.map((f, i) => (
                  <div key={i} className="file-item">
                    <File size={13} className="file-item-icon" />
                    <span className="file-item-name">{f.name}</span>
                    <span className="file-item-size">{(f.size / 1024).toFixed(0)} KB</span>
                    <button className="file-item-remove" onClick={() => removeFile(i)}><X size={12} /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="modal-btn-cancel" onClick={onClose}>取消</button>
          <button className="modal-btn-submit" onClick={handleSubmit} disabled={!title.trim()}>创建</button>
        </div>
      </div>
    </div>
  );
}
