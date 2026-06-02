export function shouldShowRunPrompt(rawStatus) {
  return ['created', 'cancelled', 'waiting_for_user'].includes(rawStatus);
}

export function getDocumentActionLabel({ done }) {
  return done ? '查看文档' : '打开文档';
}
