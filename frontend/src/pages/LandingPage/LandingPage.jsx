import React, { useEffect, useState, useRef } from 'react';
import { ArrowUp, Zap, Search, Database, Paperclip, MoreHorizontal, ArrowRight, Loader, ChevronDown, Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiPost, apiUpload } from '../../api';
import './landing-page.css';

const suggestions = [
  { icon: '📖', label: '生成一份关于节点池扩缩容机制的操作手册' },
  { icon: '📊', label: '创建一份积分防刷网关的产品需求文档' },
  { icon: '🔍', label: '搜索知识库并生成技术方案摘要' },
];

const chips = [
  { id: 'search', icon: <Search size={13} />, label: '联网搜索' },
  { id: 'kb', icon: <Database size={13} />, label: '知识库' },
  { id: 'attachment', icon: <Paperclip size={13} />, label: '附件' },
];

const MODELS = [
  { id: 'gpt-5.4', name: 'GPT-5.4' },
  { id: 'gpt-5.5', name: 'GPT-5.5' },
  { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-7', name: 'Claude Opus 4.7' },
  { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro' },
];

export default function LandingPage() {
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('idle'); // idle | thinking | done
  const [error, setError] = useState('');
  const [model, setModel] = useState('gpt-5.4');
  const [isModelOpen, setIsModelOpen] = useState(false);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
    if (status === 'thinking') textarea.scrollTop = 0;
  }, [value, status]);

  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = '';
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
    }
  };

  const handleSend = async (text) => {
    const msg = text || value;
    if (!msg.trim()) return;
    setValue(msg);
    setError('');
    setStatus('thinking');
    const task = await apiPost('/api/tasks', { prompt: msg, model }, null);
    const taskId = task?.taskId || task?.task_id || task?.id;
    if (taskId) {
      navigate(`/workspace/${taskId}`);
      return;
    }
    setError('任务创建失败：请确认后端 API 已启动并可访问。');
    setStatus('idle');
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="landing">
      <div className="landing-inner">
        {/* Slogan */}
        <div className="landing-hero">
          <h1 className="landing-title">我能为你做什么？</h1>
        </div>

        {/* Input */}
        <div className={`input-wrap${status === 'thinking' ? ' thinking' : ''}`}>
          <div className="input-box">
            {status === 'thinking' && (
              <Loader size={15} className="input-prefix-icon spinning" />
            )}
            <textarea
              ref={textareaRef}
              className="input-textarea"
              placeholder="分配一个任务或提问任何问题"
              value={value}
              onChange={e => setValue(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              disabled={status === 'thinking'}
            />
            <button
              className={`send-btn${value && status === 'idle' ? ' active' : ''}`}
              onClick={() => handleSend()}
              disabled={status === 'thinking'}
            >
              {status === 'thinking'
                ? <span className="thinking-dots"><span /><span /><span /></span>
                : <ArrowUp size={15} />
              }
            </button>
          </div>
          {status === 'thinking' && (
            <div className="thinking-status">
              正在分配任务给 Agent 团队…
            </div>
          )}
          {status === 'idle' && error && (
            <div className="input-error">
              {error}
            </div>
          )}
          {status === 'idle' && (
            <div className="input-footer">
              {chips.map((c, i) => (
                <button 
                  key={i} 
                  className="chip"
                  onClick={c.id === 'attachment' ? () => fileInputRef.current?.click() : undefined}
                >
                  {c.icon}{c.label}
                </button>
              ))}
              <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleUpload} />
              <div style={{ flex: 1 }} />
              
              <div className="model-selector-wrap">
                <button 
                  className={`chip-ghost model-chip ${isModelOpen ? 'active' : ''}`}
                  onClick={() => setIsModelOpen(!isModelOpen)}
                >
                  {MODELS.find(m => m.id === model)?.name || 'Default'}
                  <ChevronDown size={12} className={`model-chevron ${isModelOpen ? 'open' : ''}`} />
                </button>
                {isModelOpen && (
                  <>
                    <div className="model-dropdown-backdrop" onClick={() => setIsModelOpen(false)} />
                    <div className="model-dropdown">
                      <div className="model-dropdown-header">模型选择</div>
                      {MODELS.map(m => (
                        <div 
                          key={m.id} 
                          className={`model-item ${m.id === model ? 'selected' : ''}`}
                          onClick={() => { setModel(m.id); setIsModelOpen(false); }}
                        >
                          <span className="model-name">{m.name}</span>
                          {m.id === model && <Check size={14} className="model-check" />}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

            </div>
          )}
        </div>

        {/* Suggestions */}
        {status === 'idle' && (
          <div className="suggestions">
            {suggestions.map((s, i) => (
              <div key={i} className="suggestion-row" onClick={() => handleSend(s.label)}>
                <span className="suggestion-emoji">{s.icon}</span>
                <span className="suggestion-text">{s.label}</span>
                <ArrowRight size={13} className="suggestion-arrow" />
              </div>
            ))}
            <div className="suggestion-row text-tertiary">
              <MoreHorizontal size={14} />
              <span className="suggestion-text">连接你的工具以获得更好的回答</span>
              <ArrowRight size={13} className="suggestion-arrow" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
