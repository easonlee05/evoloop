import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiGet, apiPost, apiPut, apiUrl, apiUpload } from '../../api';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import {
  appendQuoteDraft,
  buildDecisionPayload,
  buildQuoteDraft,
  buildQuoteTooltipLines,
  clearQuoteDraft,
  getQuoteTooltipLineClamp,
  summarizeQuoteDraft,
} from './quoteSelection';
import { shouldAutoOpenDocument, shouldAutoRunTaskOnOpen } from './workspaceSession';
import { getDocumentActionLabel, shouldShowRunPrompt } from './workspaceActions';
import {
  Zap, Settings2, Maximize2,
  Bold, Italic, Underline, List, Code,
  Mic, Paperclip, Wrench, Send, ChevronDown,
  RotateCcw, Share2, MessageSquare,
  Square, CheckCircle2, ChevronRight, X,
  Briefcase, Terminal, ShieldCheck, PenTool, Bot,
  BookOpen, Pencil, PanelRightOpen
} from 'lucide-react';

function getAgentAvatar(avatarStr) {
  let bgColor = '#f4f4f5'; 
  let iconColor = '#52525b';
  let IconCmp = Bot;
  
  if (avatarStr === 'PM') {
    bgColor = '#f3e8ff'; // pastel purple
    iconColor = '#7e22ce'; // deep purple
    IconCmp = Briefcase;
  } else if (avatarStr === 'T' || avatarStr === 'Tech') {
    bgColor = '#e0f2fe'; // pastel blue
    iconColor = '#0369a1'; // deep blue
    IconCmp = Terminal;
  } else if (avatarStr === 'QA') {
    bgColor = '#ffedd5'; // pastel orange
    iconColor = '#c2410c'; // deep orange
    IconCmp = ShieldCheck;
  } else if (avatarStr === 'W' || avatarStr === 'Writer') {
    bgColor = '#dcfce3'; // pastel green
    iconColor = '#15803d'; // deep green
    IconCmp = PenTool;
  }
  
  return (
    <div className="msg-avatar-inner" style={{ backgroundColor: bgColor, color: iconColor }}>
      <IconCmp size={14} strokeWidth={2.5} />
    </div>
  );
}

function LiveTimer({ startTime, endTime }) {
  const [duration, setDuration] = useState('00:00');
  
  useEffect(() => {
    if (!startTime) return;
    const start = new Date(startTime).getTime();
    
    const update = () => {
      let end = endTime ? new Date(endTime).getTime() : Date.now();
      let diff = end - start;
      if (diff < 0) diff = 0;
      const totalSecs = Math.floor(diff / 1000);
      const m = Math.floor(totalSecs / 60);
      const s = totalSecs % 60;
      setDuration(`${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`);
    };
    
    update();
    if (endTime) return;
    
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [startTime, endTime]);
  
  return <span>{duration}</span>;
}

function cleanContent(text) {
  if (!text) return '';
  return text.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '').replace(/^\s+|\s+$/g, '');
}

function getSelectionRect(selection) {
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  if (rect && (rect.width || rect.height)) {
    return rect;
  }
  const rects = range.getClientRects();
  return rects.length ? rects[0] : null;
}

function QuoteTooltip({ quoteDraft }) {
  const lines = buildQuoteTooltipLines(quoteDraft);
  if (!lines.length) return null;
  const lineClamp = getQuoteTooltipLineClamp(quoteDraft.items.length);

  const tooltipTextByIndex = new Map();
  for (let index = 0; index < lines.length; index += 2) {
    tooltipTextByIndex.set(index / 2, lines[index + 1]);
  }

  return (
    <div className="quote-tooltip" role="tooltip">
      {quoteDraft.items.map((item, index) => (
        <div className="quote-tooltip-item" key={`${item.sourceId}-${index}-${item.text}`}>
          <div className="quote-tooltip-label">{item.sourceLabel}</div>
          <div className="quote-tooltip-text" style={{ WebkitLineClamp: lineClamp }}>{tooltipTextByIndex.get(index)}</div>
        </div>
      ))}
    </div>
  );
}

function readMessageSelection(selection) {
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const container = range.commonAncestorContainer;
  const element = container.nodeType === Node.ELEMENT_NODE ? container : container.parentElement;
  const messageNode = element?.closest?.('[data-quote-source="message"]');
  if (!messageNode) return null;
  const text = selection.toString().trim();
  if (!text) return null;

  return buildQuoteDraft({
    sourceType: 'message',
    sourceId: messageNode.getAttribute('data-message-id') || 'message',
    sourceLabel: messageNode.getAttribute('data-agent-name') || '会话消息',
    text,
  });
}

import './workspace.css';

// Agent 剧本：模拟多轮讨论
const SCRIPT = [
  {
    agent: 'PM Agent', role: '起草中', avatar: 'PM', color: '#7c3aed',
    delay: 600,
    content: '**PRD草案：积分防刷网关**\n\n**目标**：拦截作弊积分获取，降低薅羊毛损失，保障正常用户体验。\n\n**流程**：用户请求积分任务/发奖 -> 网关校验 -> 风控决策（放行/拦截/降级/二审） -> 结果回传业务方。\n\n**核心功能**：\n1. 多维识别：账号、设备、IP、行为频次、任务路径。\n2. 规则引擎：阈值、黑白名单、场景规则配置。\n3. 实时策略：高危拦截，中危验证码/延迟发放，低危放行。\n4. 审计监控：命中日志、告警、报表、误杀复核。\n\n**指标**：作弊拦截率、误杀率、积分损失率、接口耗时。',
    highlights: {
      label: '初步草案生成', color: '#7c3aed',
      items: ['请 Tech 确认性能指标与熔断策略', '请 QA 确认风控策略及误杀兜底机制'],
    },
  },
  {
    agent: 'Tech Agent', role: '评估中', avatar: 'T', color: '#2563eb',
    delay: 2200,
    content: '技术视角补充：\n1. 网关必须增加**幂等校验**，防止接口被恶意重放。\n2. 风控决策必须有**熔断降级**机制：若超时（> 200ms）建议默认放行，避免拖垮主业务，事后异步打标。\n3. **防锁死机制**：并发扣减积分时，分布式锁必须设置合理的 TTL（如 3-5 秒）配合 Watch Dog 防死锁。\n4. 接口耗时建议明确指标：P95 延迟需控制在 100ms 以内。',
    highlights: {
      label: '技术建议', color: '#2563eb',
      items: ['降级策略：默认放行+异步打标', '防锁死：合理TTL+看门狗', '明确 P95 < 100ms'],
    },
  },
  {
    agent: 'QA Agent', role: '评估中', avatar: 'QA', color: '#dc2626',
    delay: 2000,
    content: '质量视角补充：\n1. 需要把“杜绝重复发奖”列入核心目标。\n2. 为了防黑产缓存穿透，建议黑白名单增加**布隆过滤器**。\n3. 建议新规则上线支持**影子模式 (Shadow Mode)**，只记日志不真拦截，确认无误杀后再切正态。\n4. 拦截和降级操作必须 100% 日志留存，以备后期审计。',
    highlights: {
      label: '质量建议', color: '#dc2626',
      items: ['防缓存穿透 (布隆过滤器)', '影子模式预热', '100% 审计留痕'],
    },
  },
  {
    agent: 'PM Agent', role: '整合中', avatar: 'PM', color: '#7c3aed',
    delay: 2400,
    content: '综合技术与 QA 的建议，已输出包含「熔断降级、防死锁、防穿透、影子模式」的 PRD 初稿（见右侧文档区）。\n大家请再审阅一下完整初稿。',
    highlights: null,
    isFinal: false,
  },
  {
    agent: 'QA Agent', role: '复核中', avatar: 'QA', color: '#dc2626',
    delay: 2000,
    content: '初稿已审阅。防死锁和影子模式的加入让方案健壮了很多。但“业务流水唯一”在落地上需要确保上下游传参一致，建议在文档补充对于业务方接入规范的说明。其余无异议。',
    highlights: {
      label: '二审意见', color: '#dc2626',
      items: ['强调业务方接入规范', '其余逻辑符合预期'],
    },
  },
  {
    agent: 'PM Agent', role: '定稿中', avatar: 'PM', color: '#7c3aed',
    delay: 2200,
    content: '**PRD核心定稿**\n\n**目标**：拦截作弊积分、杜绝重复发奖、控制误杀。\n**流程**：积分请求 -> 网关幂等校验 -> 特征/规则决策(支持影子模式) -> 放行/拦截/降级/二审 -> 审计留痕。\n**功能**：账号/设备/IP/频次识别；黑白名单(含布隆过滤)；验证码/延迟发放；日志、告警、复核。\n**要求**：业务流水唯一，分布式锁防死锁；风控超时触发熔断，默认放行并异步打标。\n**指标**：P95 < 100ms，日志留存100%，重复发奖率趋零，监控拦截率/误杀率/降级命中率。',
    highlights: null,
    isFinal: true,
  }
];

const DOC = `# 产品需求文档（PRD）：积分防刷网关

## 1. 概述

积分防刷网关作为业务层与奖励发放层之间的前置风控拦截系统，旨在通过多维特征识别和实时规则引擎，有效拦截黑产薅羊毛行为，保障平台营销资金安全和正常用户体验。

## 2. 核心目标

- **拦截作弊积分获取**：降低平台资金损失。
- **杜绝重复发奖**：确保高并发下的资金发放一致性。
- **控制误杀率**：提供完善的验证与申诉机制，保障真实用户体验。

## 3. 业务流程

1. **积分请求接收**：上游业务方发起发奖或积分任务完成请求。
2. **网关幂等校验**：基于唯一的业务流水号进行防重放校验，并发扣减采用分布式锁（TTL 3-5秒 + Watch Dog）防死锁。
3. **特征与规则决策**：对账号、设备、IP、频次等进行多维度识别。黑白名单采用布隆过滤器防缓存穿透。
4. **风控动作下发**：根据决策结果执行：放行 / 拦截 / 降级（如图形验证码、延迟发放） / 触发人工二审。支持**影子模式**预热新规则。
5. **审计留痕与回传**：保存全链路日志（100%留存），并将最终结果回传业务方。

## 4. 非功能性要求

- **高可用与熔断降级**：风控引擎决策若超时（>200ms）需自动熔断。降级策略为**默认放行，异步打标**，绝不阻塞主业务线。
- **接入规范**：业务侧必须传入规范的流水ID与设备指纹信息。
- **性能指标**：核心决策接口 P95 耗时 < 100ms。

## 5. 成功指标

| 指标维度 | 监控指标 | 目标值 |
|---------|---------|--------|
| **性能** | P95 延迟 | < 100ms |
| **质量** | 重复发奖率 | 趋近于 0 |
| **风控** | 日志留存率 | 100% |
| **运营** | 拦截率/误杀率/降级命中率 | 建立看板，每周回归 |
`;

function TiptapEditor({ content, onChange, onBlur, onQuoteSelection }) {
  const editor = useEditor({
    extensions: [StarterKit, Markdown],
    content,
    editorProps: {
      attributes: {
        class: 'doc-editor markdown-body',
        style: 'outline: none; min-height: 100%;'
      },
    },
    onUpdate: ({ editor }) => {
      onChange(editor.storage.markdown.getMarkdown());
    },
    onBlur: ({ editor }) => {
      if (onBlur) onBlur(editor.storage.markdown.getMarkdown());
    },
  });

  useEffect(() => {
    if (editor && content !== editor.storage.markdown.getMarkdown()) {
      if (!editor.isFocused) {
        editor.commands.setContent(content);
      }
    }
  }, [content, editor]);

  useEffect(() => {
    if (!editor || !onQuoteSelection) return undefined;

    const onMouseUp = () => {
      const { from, to } = editor.state.selection;
      if (from === to) {
        onQuoteSelection(null);
        return;
      }
      const selectedText = editor.state.doc.textBetween(from, to, '\n').trim();
      if (!selectedText) {
        onQuoteSelection(null);
        return;
      }

      const selection = window.getSelection();
      const rect = getSelectionRect(selection);
      onQuoteSelection({
        draft: buildQuoteDraft({
          sourceType: 'editor',
          sourceId: 'workspace-editor',
          sourceLabel: '文档编辑区',
          text: selectedText,
        }),
        rect,
      });
    };

    const dom = editor.view.dom;
    dom.addEventListener('mouseup', onMouseUp);
    return () => {
      dom.removeEventListener('mouseup', onMouseUp);
    };
  }, [editor, onQuoteSelection]);

  return (
    <>
      <EditorContent editor={editor} style={{ height: '100%' }} />
    </>
  );
}

export default function Workspace() {
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState('');
  const [isLive, setIsLive]         = useState(true);
  const [interrupted, setInterrupted] = useState(false);
  const [typing, setTyping]           = useState(null);
  const [toast, setToast]           = useState(null);
  const [done, setDone]             = useState(false);
  const [taskStatus, setTaskStatus] = useState(null);
  const [docOpen, setDocOpen]       = useState(false);
  const [docFullscreen, setDocFullscreen] = useState(false);
  const [doc, setDoc]               = useState(DOC);
  const { id: taskId }               = useParams();
  const [saved, setSaved]           = useState(true);
  const [taskTitle, setTaskTitle]   = useState('AI 协作直播');
  const [isEditing, setIsEditing]   = useState(false);
  const [knowledgeHint, setKnowledgeHint] = useState(null);
  const [knowledgePreview, setKnowledgePreview] = useState([]);
  const [quoteDraft, setQuoteDraft] = useState(null);
  const [selectionAction, setSelectionAction] = useState(null);
  const [hasUserOpenedDoc, setHasUserOpenedDoc] = useState(false);
  
  const savedRef = useRef(saved);
  useEffect(() => {
    savedRef.current = saved;
  }, [saved]);

  const messagesEndRef = useRef(null);
  const timerRef       = useRef(null);
  const typeTimerRef   = useRef(null);
  const streamRef      = useRef(null);
  const fileInputRef   = useRef(null);
  const writerMsgIdRef = useRef(null);
  const startTimeRef   = useRef(null);
  const agentStartTimeRef = useRef({});
  const chatRef = useRef(null);
  const knowledgeToastTimerRef = useRef(null);

  const showKnowledgeToast = (message) => {
    if (!message) return;
    setToast({ type: 'knowledge', message });
    clearTimeout(knowledgeToastTimerRef.current);
    knowledgeToastTimerRef.current = setTimeout(() => setToast(null), 3200);
  };

  const formatRelativeTime = (timeStr) => {
    if (!startTimeRef.current) return '00:00';
    let msgTime = Date.now();
    if (timeStr) {
      msgTime = new Date(timeStr).getTime();
    }
    let diff = msgTime - startTimeRef.current;
    if (diff < 0) diff = 0;
    const totalSecs = Math.floor(diff / 1000);
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const dismissSelectionAction = () => {
    setSelectionAction(null);
  };

  const handleQuoteSelection = (selectionPayload) => {
    if (!selectionPayload?.draft || !selectionPayload?.rect) {
      dismissSelectionAction();
      return;
    }

    setSelectionAction({
      draft: selectionPayload.draft,
      top: Math.max(selectionPayload.rect.top + window.scrollY - 54, 16),
      left: selectionPayload.rect.left + window.scrollX + (selectionPayload.rect.width / 2),
    });
  };

  const applySelectionQuote = () => {
    if (!selectionAction?.draft) return;
    setQuoteDraft(prev => appendQuoteDraft(prev, selectionAction.draft));
    dismissSelectionAction();
    window.getSelection()?.removeAllRanges();
  };

  const handleClearQuoteDraft = () => {
    setQuoteDraft(clearQuoteDraft());
  };

  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = '';
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  useEffect(() => {
    const onPointerUp = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || !chatRef.current?.contains(selection.anchorNode)) {
        return;
      }

      const draft = readMessageSelection(selection);
      const rect = getSelectionRect(selection);
      if (!draft || !rect) return;

      handleQuoteSelection({ draft, rect });
    };

    const onPointerDown = (event) => {
      if (event.target.closest('.selection-action-popover') || event.target.closest('.quote-draft-pill')) {
        return;
      }
      dismissSelectionAction();
    };

    document.addEventListener('mouseup', onPointerUp);
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('mouseup', onPointerUp);
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, []);

  useEffect(() => {
    setMessages([]);
    setDoc('');
    setDone(false);
    setTaskStatus(null);
    setIsLive(false);
    setTyping(null);
    setToast(null);
    setInterrupted(false);
    setQuoteDraft(null);
    setSelectionAction(null);
    setDocOpen(false);
    setDocFullscreen(false);
    setIsEditing(false);
    setHasUserOpenedDoc(false);
    startTimeRef.current = Date.now();

    if (!taskId || taskId === 'new') {
      setTaskTitle('新建任务');
      setDoc(DOC);
      playNext(0);
      return () => { clearTimeout(timerRef.current); clearTimeout(typeTimerRef.current); };
    }

    startTimeRef.current = null; // Reset to null so first event sets it

    let closed = false;
    apiGet(`/api/tasks/${taskId}`, null).then(data => {
      if (closed) return;
      if (data && data.title) {
        setTaskTitle(data.title);
      }
      if (data?.knowledge_status?.state === 'error') {
        const fallbackMsg = data.knowledge_status.error
          ? `知识库出了点问题，暂时没法帮你查资料：${data.knowledge_status.error}`
          : '知识库出了点问题，当前任务会先在没有资料辅助的情况下继续执行';
        setKnowledgeHint(fallbackMsg);
        showKnowledgeToast(fallbackMsg);
        setKnowledgePreview(data.knowledge_status.preview || []);
      } else if (data?.knowledge_status?.state === 'ready') {
        const message = `已帮你查到 ${data.knowledge_status.items} 条相关资料，Agent 会参考这些内容继续工作`;
        setKnowledgeHint(message);
        showKnowledgeToast(message);
        setKnowledgePreview(data.knowledge_status.preview || []);
      } else if (data?.knowledge_status?.state === 'no_results') {
        const message = '知识库连接正常，但这次暂时没搜到特别相关的资料，Agent 会继续自行生成内容';
        setKnowledgeHint(message);
        showKnowledgeToast(message);
        setKnowledgePreview([]);
      } else {
        setKnowledgeHint(null);
        setKnowledgePreview([]);
      }
      
      if (data && shouldAutoRunTaskOnOpen({ rawStatus: data.raw_status })) {
        apiPost(`/api/tasks/${taskId}/run`, {}, null).catch(e => console.error("run error", e));
      }
      
      const isFinished = data && ['completed', 'cancelled', 'failed'].includes(data.raw_status);
      setTaskStatus(data?.raw_status || null);
      setIsLive(!isFinished);
      setDone(data && data.raw_status === 'completed');
      
      connectStream(taskId);
      loadDocument(taskId);
    });

    apiGet('/api/knowledge/health', null).then(data => {
      if (closed || !data) return;
      if (data.status === 'degraded') {
        const msg = data.error ? `知识库服务异常：${data.error}` : '知识库服务当前不可用';
        setKnowledgeHint(msg);
        showKnowledgeToast(msg);
      } else if (!knowledgeHint && data.status === 'ok') {
        setKnowledgeHint('知识库连接正常，任务开始后会自动尝试查找相关资料');
      }
    });

    return () => {
      closed = true;
      if (streamRef.current) streamRef.current.close();
      clearTimeout(timerRef.current);
      clearTimeout(typeTimerRef.current);
      clearTimeout(knowledgeToastTimerRef.current);
    };
  }, [taskId]);


  function connectStream(id) {
    if (streamRef.current) streamRef.current.close();
    const source = new EventSource(apiUrl(`/api/tasks/${id}/events`));
    streamRef.current = source;
    source.onmessage = handleStreamEvent;
    source.addEventListener('workflow.step.started', handleStreamEvent);
    source.addEventListener('workflow.step.completed', handleStreamEvent);
    source.addEventListener('agent.message.chunk', handleStreamEvent);
    source.addEventListener('agent.message.completed', handleStreamEvent);
    source.addEventListener('arbitration.requested', handleStreamEvent);
    source.addEventListener('artifact.created', handleStreamEvent);
    source.addEventListener('task.completed', handleStreamEvent);
    source.addEventListener('task.cancelled', handleStreamEvent);
    source.addEventListener('task.failed', handleStreamEvent);
    source.addEventListener('tool.call.denied', handleStreamEvent);
    source.addEventListener('model.fallback', handleStreamEvent);
    source.onerror = () => {
      source.close();
      setTimeout(() => loadStoredMessages(id), 250);
    };
  }

  async function loadStoredMessages(id) {
    const result = await apiGet(`/api/tasks/${id}/messages`, { messages: [] });
    if (result.messages?.length) {
      if (result.messages[0].created_at) {
        startTimeRef.current = new Date(result.messages[0].created_at).getTime();
      }
      const formatted = result.messages.map(msg => ({
        ...msg,
        time: msg.created_at ? formatRelativeTime(msg.created_at) : msg.time
      }));
      setMessages(formatted);
      if (formatted.some(message => message.isFinal)) {
        setIsLive(false);
        setDone(true);
        setTaskStatus('completed');
      }
    }
  }

  function handleStreamEvent(event) {
    const data = JSON.parse(event.data);
    const message = data.frontend_message;
    if (!message) return;
    
    if (message.created_at && !startTimeRef.current) {
      startTimeRef.current = new Date(message.created_at).getTime();
    }
    
    if (message.type === 'toast') {
      setToast({ type: 'default', message: message.content });
      setTimeout(() => setToast(null), 3000);
      return;
    }

    const isWriter = message.agent?.toLowerCase().includes('writer') || message.avatar === 'W' || message.avatar === 'Writer';

    if (isWriter) {
      if (shouldAutoOpenDocument({ reason: 'writer-event', hasUserOpenedDoc })) {
        setDocOpen(true);
      }
      if (message.type === 'typing') {
        writerMsgIdRef.current = message.id;
        setDoc('');
      } else if (message.type === 'chunk') {
        if (writerMsgIdRef.current !== message.id) {
          writerMsgIdRef.current = message.id;
          setDoc(cleanContent(message.content));
        } else {
          setDoc(prev => cleanContent((prev || '') + message.content));
        }
      } else {
        if (message.content && writerMsgIdRef.current !== message.id) {
          writerMsgIdRef.current = message.id;
          setDoc(cleanContent(message.content));
        }
      }
      
      if (message.isFinal) {
        setIsLive(false);
        setDone(true);
        setTaskStatus('completed');
        if (taskId && taskId !== 'new') loadDocument(taskId);
        if (streamRef.current) streamRef.current.close();
      }
      return;
    }
    
    if (message.type === 'typing') {
      agentStartTimeRef.current[message.agent] = message.created_at || new Date().toISOString();
      setTyping({
        agent: message.agent,
        role: message.role,
        avatar: message.avatar,
        color: message.color,
        isThinking: true,
        text: '',
        created_at: message.created_at
      });
      return;
    }
    
    if (message.type === 'chunk') {
      if (!agentStartTimeRef.current[message.agent]) {
        agentStartTimeRef.current[message.agent] = message.created_at || new Date().toISOString();
      }
      setTyping(prev => {
        if (!prev || prev.agent !== message.agent) {
          return {
            agent: message.agent,
            role: message.role,
            avatar: message.avatar,
            color: message.color,
            isThinking: false,
            text: message.content,
            created_at: message.created_at
          };
        }
        return { ...prev, isThinking: false, text: (prev.text || '') + message.content };
      });
      return;
    }
    
    setTyping(null);
    const msgStartTime = agentStartTimeRef.current[message.agent];
    if (msgStartTime) {
      delete agentStartTimeRef.current[message.agent];
    }
    const msgToSave = { 
      ...message, 
      startTime: msgStartTime,
      time: message.created_at ? formatRelativeTime(message.created_at) : message.time 
    };
    setMessages(prev => prev.some(item => item.id === msgToSave.id) ? prev : [...prev, msgToSave]);
    if (msgToSave.isFinal) {
      setIsLive(false);
      setDone(true);
      setTaskStatus('completed');
      if (taskId && taskId !== 'new') loadDocument(taskId);
      if (streamRef.current) streamRef.current.close();
    }
  }

  function handleRunTask() {
    if (!taskId || taskId === 'new') return;
    setInterrupted(false);
    setIsLive(true);
    setTaskStatus('running');
    apiPost(`/api/tasks/${taskId}/run`, {}, null).catch(e => console.error('run error', e));
  }

  function handleOpenDocument() {
    setHasUserOpenedDoc(true);
    setDocOpen(true);
  }

  async function loadDocument(id) {
    const result = await apiGet(`/api/tasks/${id}/document`, null);
    if (result && typeof result.content === 'string') {
      setDoc(result.content);
      setSaved(true);
    }
  }

  function playNext(idx) {
    if (idx >= SCRIPT.length) return;
    const step = SCRIPT[idx];
    timerRef.current = setTimeout(() => {
      typeMessage(step, idx);
    }, step.delay);
  }

  function typeMessage(step, idx) {
    const full = step.content;
    let i = 0;
    setTyping({ agent: step.agent, avatar: step.avatar, color: step.color, role: step.role, text: '', full });

    function tick() {
      i += Math.floor(Math.random() * 3) + 2; // 每次打 2-4 个字
      const text = full.slice(0, Math.min(i, full.length));
      setTyping(prev => prev ? { ...prev, text } : null);
      if (i < full.length) {
        typeTimerRef.current = setTimeout(tick, 30);
      } else {
        // 打字完成，提交消息
        setTyping(null);
        const msg = { ...step, id: Date.now(), content: full, time: formatRelativeTime(null) };
        setMessages(prev => [...prev, msg]);
        if (step.isFinal) {
          setIsLive(false);
          setDone(true);
        } else {
          playNext(idx + 1);
        }
      }
    }
    typeTimerRef.current = setTimeout(tick, 30);
  }

  // 打断
  function handleInterrupt() {
    clearTimeout(timerRef.current);
    clearTimeout(typeTimerRef.current);
    if (taskId && taskId !== 'new') apiPost(`/api/tasks/${taskId}/interrupt`, {}, null);
    setTyping(null);
    setIsLive(false);
    setInterrupted(true);
  }

  // 恢复
  function handleResume() {
    setInterrupted(false);
    setIsLive(true);
    const nextIdx = messages.length; // 从下一条继续
    if (nextIdx < SCRIPT.length) playNext(nextIdx);
  }

  // 发送指令
  function handleSend() {
    if (!input.trim() && !quoteDraft?.items?.length) return;
    const instruction = input;
    const userMsg = {
      id: Date.now(), isUser: true,
      content: instruction,
      time: formatRelativeTime(null),
      quotedSelections: quoteDraft?.items || [],
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    if (taskId && taskId !== 'new') {
      apiPost(`/api/tasks/${taskId}/decisions`, buildDecisionPayload(instruction, quoteDraft), null);
    }
    setQuoteDraft(null);
    dismissSelectionAction();
    // 恢复讨论
    if (interrupted) {
      setTimeout(() => {
        setInterrupted(false);
        setIsLive(true);
        const nextIdx = messages.length + 1;
        if (nextIdx < SCRIPT.length) playNext(nextIdx);
      }, 800);
    }
  }

  function saveDocument(content) {
    if (savedRef.current) return;
    if (!taskId || taskId === 'new') {
      setSaved(true);
      return;
    }
    apiPut(`/api/tasks/${taskId}/document`, { content }, null).then(() => setSaved(true));
  }

  return (
    <div className={`workspace${docOpen ? ' doc-open' : ''}${docFullscreen ? ' doc-fullscreen' : ''}`}>
      {selectionAction && (
        <button
          className="selection-action-popover"
          style={{ top: selectionAction.top, left: selectionAction.left }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={applySelectionQuote}
        >
          <MessageSquare size={16} />
          <span>添加到对话</span>
        </button>
      )}

      {/* 中间：AI 协作直播 */}
      <div className="ws-chat" ref={chatRef}>
        <div className="ws-chat-header">
          <div className="ws-chat-title">
            <span>{taskTitle}</span>
            {isLive && !interrupted && (
              <span className="live-badge"><span className="live-dot" />直播中</span>
            )}
            {interrupted && (
              <span className="paused-badge">已暂停</span>
            )}
          </div>
          <div className="ws-chat-header-actions">
            <button className="icon-btn" onClick={handleOpenDocument} title={getDocumentActionLabel({ done })}>
              <PanelRightOpen size={15} />
            </button>
            <button className="icon-btn"><Settings2 size={15} /></button>
          </div>
        </div>

        <div className="ws-chat-notice">
          <Zap size={13} />
          <span>多智能体协同讨论中，您可随时打断并下达指令</span>
          <div className="ws-chat-notice-actions">
            {shouldShowRunPrompt(taskStatus) ? (
              <button className="notice-action-btn" onClick={handleRunTask}>继续执行</button>
            ) : null}
          </div>
        </div>

        <div className="ws-messages">
          {toast && (
            <div className={`workspace-toast${toast.type === 'knowledge' ? ' workspace-toast-knowledge' : ''}`}>
              {toast.type === 'knowledge' ? <BookOpen size={14} /> : <span>⚠️</span>}
              <span>{toast.message}</span>
            </div>
          )}

          {messages.map(msg => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {/* 正在打字的消息 */}
          {typing && (
            <div className="msg">
              <div className="msg-avatar">
                {getAgentAvatar(typing.avatar)}
              </div>
              <div className="msg-body">
                <div className="msg-header">
                  <span className="msg-agent">{typing.agent}</span>
                  <span className="msg-role">{typing.role}</span>
                  <span className="msg-time">
                    <LiveTimer startTime={agentStartTimeRef.current[typing.agent] || typing.created_at} />
                  </span>
                  <button className="interrupt-btn" onClick={handleInterrupt}>
                    <Square size={10} />打断
                  </button>
                </div>
                <div className="msg-content markdown-body">
                  {typing.isThinking ? (
                    <div className="thinking-dots-wrap" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-tertiary)' }}>
                      <span className="thinking-dots"><span /><span /><span /></span>
                      <span style={{ fontSize: '13px' }}>深度思考中...</span>
                    </div>
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {cleanContent(typing.text) + '▋'}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            </div>
          )}


          {/* 打断提示 */}
          {interrupted && (
            <div className="interrupt-notice">
              <span>讨论已暂停，输入指令后继续</span>
              <button className="resume-btn" onClick={handleResume}>继续讨论</button>
            </div>
          )}

          {/* 完成卡片 */}
          {done && !docOpen && (
            <div className="done-card" onClick={handleOpenDocument}>
              <div className="done-card-left">
                <CheckCircle2 size={18} className="done-icon" />
                <div>
                  <div className="done-title">PRD 初稿已生成</div>
                  <div className="done-sub">产品需求文档（PRD）- EvoLoop 智能进化平台</div>
                </div>
              </div>
              <div className="done-card-right">
                <span>查看文档</span>
                <ChevronRight size={14} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入框 */}
        <div className="ws-input-wrap">
          <div className="ws-input-box">
            {quoteDraft?.items?.length ? (
              <div className="quote-draft-pill quote-draft-pill-with-tooltip">
                <div className="quote-draft-pill-main">
                  <MessageSquare size={15} />
                  <span>{summarizeQuoteDraft(quoteDraft)}</span>
                </div>
                <button className="quote-draft-pill-remove" onClick={handleClearQuoteDraft} aria-label="移除引用">
                  <X size={14} />
                </button>
                <QuoteTooltip quoteDraft={quoteDraft} />
              </div>
            ) : null}
            <div className="ws-input-row">
              <textarea
                className="ws-input"
                placeholder={interrupted ? '输入指令，Agent 将根据你的指令继续…' : '向 EvoLoop 发送指令…'}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                rows={1}
              />
              <button className={`ws-send${input || quoteDraft?.items?.length ? ' active' : ''}`} onClick={handleSend}>
                <Send size={14} />
              </button>
            </div>
          </div>
          <div className="ws-input-tools">
            <button className="tool-btn"><Mic size={13} /></button>
            <button className="tool-btn" onClick={() => fileInputRef.current?.click()}>
              <Paperclip size={13} />上传文件<ChevronDown size={11} />
            </button>
            <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleUpload} />
            <button className="tool-btn"><Wrench size={13} />调用工具<ChevronDown size={11} /></button>
          </div>
        </div>
      </div>

      {/* 右侧：文档区（仅 docOpen 时展示） */}
      {docOpen && (
        <div className="ws-doc">
          <div className="ws-doc-header">
            <div className="ws-doc-title-row">
              <Zap size={14} className="doc-title-icon" />
              <span className="doc-title">产品需求文档（PRD）</span>
              <span className={`save-status${saved ? ' saved' : ''}`}>{saved ? '已保存' : '未保存'}</span>
            </div>
            <div className="ws-doc-actions">
              <button
                className="icon-btn"
                onClick={() => { setHasUserOpenedDoc(true); setIsEditing(!isEditing); }}
                title={isEditing ? '预览阅读' : '编辑源码'}
              >
                {isEditing ? <BookOpen size={14} /> : <Pencil size={14} />}
              </button>
              <button className="icon-btn"><Share2 size={14} /></button>
              <button className="icon-btn"><MessageSquare size={14} /></button>
              <button className="icon-btn" onClick={() => setDocFullscreen(f => !f)} title={docFullscreen ? '退出全屏' : '全屏编辑'}>
                <Maximize2 size={14} />
              </button>
              <button className="icon-btn" onClick={() => { setDocOpen(false); setDocFullscreen(false); }}><X size={14} /></button>
            </div>
          </div>

          <div className="doc-toolbar">
            <button className="icon-btn"><RotateCcw size={13} /></button>
            <div className="toolbar-sep" />
            <select className="toolbar-select">
              <option>正文</option>
              <option>标题 1</option>
              <option>标题 2</option>
              <option>标题 3</option>
              <option>标题 4</option>
            </select>
            <div className="toolbar-sep" />
            <button className="icon-btn"><Bold size={13} /></button>
            <button className="icon-btn"><Italic size={13} /></button>
            <button className="icon-btn"><Underline size={13} /></button>
            <div className="toolbar-sep" />
            <button className="icon-btn"><List size={13} /></button>
            <button className="icon-btn"><Code size={13} /></button>
          </div>

          <div className="doc-body">
            {isEditing ? (
              <TiptapEditor
                key={taskId}
                content={doc}
                onChange={newDoc => { setDoc(newDoc); setSaved(false); }}
                onBlur={newDoc => saveDocument(newDoc)}
                onQuoteSelection={handleQuoteSelection}
              />
            ) : (
              <div className="doc-preview" onClick={() => { setHasUserOpenedDoc(true); setDocOpen(true); setIsEditing(true); }}>
                <DocRenderer content={doc} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }) {
  if (msg.isUser) {
    return (
      <div className="msg msg-user">
        <div className="msg-user-stack">
          {msg.quotedSelections?.length ? (
            <div className="quote-draft-pill quote-draft-pill-inline quote-draft-pill-with-tooltip">
              <div className="quote-draft-pill-main">
                <MessageSquare size={15} />
                <span>{msg.quotedSelections.length} 个已选文本片段</span>
              </div>
              <QuoteTooltip quoteDraft={{ items: msg.quotedSelections }} />
            </div>
          ) : null}
          {msg.content ? <div className="msg-user-bubble">{msg.content}</div> : null}
        </div>
      </div>
    );
  }
  return (
    <div className="msg">
      <div className="msg-avatar">
        {getAgentAvatar(msg.avatar)}
      </div>
      <div className="msg-body">
        <div className="msg-header">
          <span className="msg-agent">{msg.agent}</span>
          <span className="msg-role">{msg.role}</span>
          <span className="msg-time">
            {msg.startTime ? <LiveTimer startTime={msg.startTime} endTime={msg.created_at || new Date().toISOString()} /> : msg.time}
          </span>
        </div>
        <div
          className="msg-content markdown-body"
          data-quote-source="message"
          data-message-id={msg.id}
          data-agent-name={msg.agent || msg.role || '会话消息'}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanContent(msg.content)}</ReactMarkdown>
        </div>
        {msg.highlights && (
          <div className="msg-highlights">
            <div className="highlights-label">{msg.highlights.label}</div>
            <ul className="highlights-list">
              {msg.highlights.items.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function DocRenderer({ content }) {
  return (
    <div className="doc-rendered markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
