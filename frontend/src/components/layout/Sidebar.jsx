import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Zap, CheckSquare, BookOpen, ShieldCheck, Archive, Settings, ChevronRight } from 'lucide-react';
import { apiGet, apiDelete } from '../../api';
import { flattenConversationGroups } from './sidebarHistory';
import './sidebar.css';

const navItems = [
  { icon: <Zap size={15} />, label: '新建任务', path: '/', primary: true },
  { icon: <CheckSquare size={15} />, label: '任务大厅', path: '/tasks' },
  { icon: <BookOpen size={15} />, label: '知识库', path: '/knowledge-base' },
  { icon: <ShieldCheck size={15} />, label: '法则审核', path: '/rule-audit', badge: true },
  { icon: <Archive size={15} />, label: '归档与回收', path: '/recycle-bin' },
];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id: activeTaskId } = useParams();
  const [today, setToday] = useState([]);
  const [yesterday, setYesterday] = useState([]);
  const [older, setOlder] = useState([]);
  const [historyError, setHistoryError] = useState(false);
  const historyItems = flattenConversationGroups({ today, yesterday, older });

  const fetchChats = () => {
    apiGet('/api/conversations/recent', null).then(data => {
      if (!data) {
        setHistoryError(true);
        setToday([]);
        setYesterday([]);
        setOlder([]);
        return;
      }
      setHistoryError(false);
      setToday(data.today || []);
      setYesterday(data.yesterday || []);
      setOlder(data.older || []);
    });
  };

  useEffect(() => {
    fetchChats();
  }, [location.pathname]);

  const handleDeleteTask = async (e, id) => {
    e.stopPropagation();
    await apiDelete(`/api/tasks/${id}`);
    fetchChats();
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-sq">E</div>
        <span className="logo-text">EvoLoop</span>
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        {navItems.map((item, i) => (
          <NavLink
            key={i}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}${item.primary ? ' nav-primary' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {item.badge === true ? (
              <span className="nav-badge-dot"></span>
            ) : item.badge ? (
              <span className="nav-badge">{item.badge}</span>
            ) : null}
          </NavLink>
        ))}
      </nav>

      {/* 最近对话 */}
      <div className="sidebar-section">
        <div className="section-row">
          <span className="section-label">最近对话</span>
          <ChevronRight size={12} className="section-arrow" />
        </div>
        <div className="sidebar-history-scroll">
          {historyError && (
            <div className="chat-empty">任务历史暂时无法加载</div>
          )}
          {!historyError && historyItems.length === 0 && (
            <div className="chat-empty">暂无任务历史</div>
          )}
          {!historyError && historyItems.map((entry, index) => entry.type === 'group' ? (
            <div key={`${entry.label}-${index}`} className="chat-group-label">{entry.label}</div>
          ) : (
            <div
              key={entry.id}
              className={`chat-item${entry.id === activeTaskId ? ' active' : ''}`}
              onClick={() => navigate(`/workspace/${entry.id}`)}
            >
              <span className="chat-label">{entry.label}</span>
              <span className="chat-time">{entry.time}</span>
              <div className="chat-actions">
                <button className="chat-action-btn" onClick={(e) => handleDeleteTask(e, entry.id)} title="归档任务">
                  <Archive size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="user-row">
          <div className="user-av">E</div>
          <span className="user-name">Eason</span>
          <Settings size={13} className="user-settings" />
        </div>
      </div>
    </aside>
  );
}
