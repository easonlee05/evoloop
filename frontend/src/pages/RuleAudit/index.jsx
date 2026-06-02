import React, { useEffect, useState } from 'react';
import { CheckCircle2, Edit3, XCircle, X } from 'lucide-react';
import { apiGet, apiPost } from '../../api';
import './rule-audit.css';

const tabs = ['待审核', '已批准', '已驳回'];

const rules = [
  {
    id: 'R-0021',
    title: '技术方案必须包含熔断降级策略',
    desc: 'AI 发现用户在 7 次评审中均手动补充了熔断降级方案，建议将其纳入技术方案的强制输出项。',
    source: '进化引擎技术方案评审',
    sourceId: 'T-0420',
    extractedAt: '今天 10:32',
    confidence: 94,
    status: 'pending',
  },
  {
    id: 'R-0020',
    title: 'PRD 成功指标需包含可量化的数值目标',
    desc: '对比 12 份 PRD 修改记录，用户始终将模糊描述替换为带具体数值的指标，如"提升用户满意度"改为"NPS ≥ 45"。',
    source: '产品需求文档 v2.0 评审',
    sourceId: 'T-0421',
    extractedAt: '今天 09:15',
    confidence: 88,
    status: 'pending',
  },
  {
    id: 'R-0019',
    title: 'Agent 协作轮次超过 3 轮时需人工介入',
    desc: '统计显示，当 PM/Tech/QA 三方讨论超过 3 轮仍未收敛时，人工介入后的方案质量显著高于继续自动推演。',
    source: 'Agent 协作流程设计',
    sourceId: 'T-0418',
    extractedAt: '昨天 16:45',
    confidence: 79,
    status: 'pending',
  },
  {
    id: 'R-0018',
    title: '安全相关需求必须经过 QA Agent 二次确认',
    desc: '发现 4 次安全漏洞均出现在 QA 未参与的评审环节，建议将安全类需求标记为 QA 强制参与。',
    source: '法则库季度审查',
    sourceId: 'T-0417',
    extractedAt: '昨天 14:20',
    confidence: 91,
    status: 'pending',
  },
];

const approvedRules = [
  { id: 'R-0017', title: '文档标题需包含版本号', source: 'T-0415', approvedAt: '3 天前', status: 'approved' },
  { id: 'R-0016', title: '技术选型需列出备选方案及取舍理由', source: 'T-0414', approvedAt: '5 天前', status: 'approved' },
];

const rejectedRules = [
  { id: 'R-0015', title: '所有任务默认启用深度思考模式', source: 'T-0413', rejectedAt: '1 周前', status: 'rejected' },
];

const confidenceColor = (v) => v >= 90 ? '#16a34a' : v >= 75 ? '#d97706' : '#dc2626';

export default function RuleAudit() {
  const [tab, setTab] = useState('待审核');
  const [statuses, setStatuses] = useState({});
  const [pendingRules, setPendingRules] = useState(rules);
  const [approvedList, setApprovedList] = useState(approvedRules);
  const [rejectedList, setRejectedList] = useState(rejectedRules);

  const [editingRule, setEditingRule] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');

  const handle = (id, action) => {
    if (action === 'rejected') apiPost(`/api/rules/${id}/reject`, {}, null);
    else apiPost(`/api/rules/${id}/approve`, {}, null);
    setStatuses(prev => ({ ...prev, [id]: action }));
  };

  const openEditModal = (rule) => {
    setEditingRule(rule);
    setEditTitle(rule.title);
    setEditDesc(rule.desc);
  };

  const handleSaveEdit = () => {
    if (!editingRule) return;
    const id = editingRule.id;
    setPendingRules(prev => prev.map(r => r.id === id ? { ...r, title: editTitle, desc: editDesc } : r));
    apiPost(`/api/rules/${id}/approve`, { title: editTitle, desc: editDesc }, null);
    setStatuses(prev => ({ ...prev, [id]: 'approved' }));
    setEditingRule(null);
  };

  useEffect(() => {
    apiGet('/api/rules?status=pending', { rules }).then(data => setPendingRules(data.rules || rules));
    apiGet('/api/rules?status=approved', { rules: approvedRules }).then(data => setApprovedList(data.rules || approvedRules));
    apiGet('/api/rules?status=rejected', { rules: rejectedRules }).then(data => setRejectedList(data.rules || rejectedRules));
  }, []);

  const pendingList = pendingRules.filter(r => !statuses[r.id]);
  const counts = {
    '待审核': pendingList.length,
    '已批准': approvedList.length + Object.values(statuses).filter(s => s === 'approved').length,
    '已驳回': rejectedList.length + Object.values(statuses).filter(s => s === 'rejected').length,
  };

  return (
    <div className="rule-page">
      <div className="rule-top">
        <div>
          <h1 className="page-title">法则审核</h1>
          <p className="page-sub">AI 从任务修改中提炼的候选法则，等待你的裁决</p>
        </div>
        <div className="rule-stats">
          {Object.entries(counts).map(([label, count]) => (
            <div key={label} className="rule-stat">
              <span className="rule-stat-num">{count}</span>
              <span className="rule-stat-label">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rule-tabs">
        {tabs.map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t}
            {counts[t] > 0 && <span className="tab-count">{counts[t]}</span>}
          </button>
        ))}
      </div>

      <div className="rule-list">
        {tab === '待审核' && pendingList.map(rule => (
          <div key={rule.id} className="rule-card">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-confidence" style={{ color: confidenceColor(rule.confidence) }}>
                  置信度 {rule.confidence}%
                </span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-desc">{rule.desc}</div>
              <div className="rule-meta">
                来源：<span className="rule-source">{rule.source}</span>
                <span className="rule-dot">·</span>
                {rule.extractedAt}
              </div>
            </div>
            <div className="rule-actions">
              <button className="rule-btn approve" onClick={() => handle(rule.id, 'approved')}>
                <CheckCircle2 size={14} />批准入库
              </button>
              <button className="rule-btn edit" onClick={() => openEditModal(rule)}>
                <Edit3 size={14} />修改后入库
              </button>
              <button className="rule-btn reject" onClick={() => handle(rule.id, 'rejected')}>
                <XCircle size={14} />驳回
              </button>
            </div>
          </div>
        ))}

        {tab === '待审核' && pendingList.length === 0 && (
          <div className="rule-empty">
            <CheckCircle2 size={32} className="empty-icon" />
            <div>全部处理完毕</div>
          </div>
        )}

        {tab === '已批准' && [...approvedList, ...pendingRules.filter(r => statuses[r.id] === 'approved')].map(rule => (
          <div key={rule.id} className="rule-card rule-card-done">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-done-badge approved">已批准</span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-meta">来源：{rule.source} · {rule.approvedAt || '刚刚'}</div>
            </div>
          </div>
        ))}

        {tab === '已驳回' && [...rejectedList, ...pendingRules.filter(r => statuses[r.id] === 'rejected')].map(rule => (
          <div key={rule.id} className="rule-card rule-card-done">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-done-badge rejected">已驳回</span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-meta">来源：{rule.source} · {rule.rejectedAt || '刚刚'}</div>
            </div>
          </div>
        ))}
      </div>

      {editingRule && (
        <div className="modal-overlay" onClick={() => setEditingRule(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">修改法则并入库</span>
              <button className="modal-close" onClick={() => setEditingRule(null)}><X size={15} /></button>
            </div>
            <div className="modal-body">
              <div className="form-field">
                <label className="form-label">法则标题</label>
                <input className="form-input" value={editTitle} onChange={e => setEditTitle(e.target.value)} />
              </div>
              <div className="form-field">
                <label className="form-label">法则描述</label>
                <textarea className="form-textarea" rows={4} value={editDesc} onChange={e => setEditDesc(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="modal-btn-cancel" onClick={() => setEditingRule(null)}>取消</button>
              <button className="modal-btn-submit" onClick={handleSaveEdit} disabled={!editTitle.trim() || !editDesc.trim()}>入库</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
