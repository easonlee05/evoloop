function normalizeText(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

function truncateQuoteText(text, maxLength = 150) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}…`;
}

function getTooltipTextBudget(itemCount) {
  if (itemCount <= 1) return 150;
  const dynamicBudget = Math.floor(220 / itemCount);
  return Math.max(48, Math.min(150, dynamicBudget));
}

export function getQuoteTooltipLineClamp(itemCount) {
  if (itemCount <= 1) return 5;
  if (itemCount === 2) return 3;
  return 2;
}

export function buildQuoteDraft({ sourceType, sourceId, sourceLabel, text }) {
  return {
    sourceType: sourceType || 'message',
    sourceId: sourceId || 'unknown',
    sourceLabel: sourceLabel || '未知来源',
    text: normalizeText(text),
  };
}

export function appendQuoteDraft(currentDraft, nextItem) {
  if (!nextItem || !nextItem.text) {
    return currentDraft || null;
  }

  const items = currentDraft?.items ? [...currentDraft.items] : [];
  const exists = items.some(
    (item) =>
      item.sourceType === nextItem.sourceType &&
      item.sourceId === nextItem.sourceId &&
      item.text === nextItem.text
  );

  if (!exists) {
    items.push(nextItem);
  }

  if (!items.length) {
    return null;
  }

  return {
    items,
    summary: summarizeQuoteDraft({ items }),
  };
}

export function summarizeQuoteDraft(draft) {
  const count = draft?.items?.length || 0;
  return `${count} 个已选文本片段`;
}

export function clearQuoteDraft() {
  return null;
}

export function buildDecisionPayload(decision, quoteDraft) {
  const payload = { decision };
  if (quoteDraft?.items?.length) {
    payload.quoted_selections = quoteDraft.items.map((item) => ({
      source_type: item.sourceType,
      source_id: item.sourceId,
      source_label: item.sourceLabel,
      text: item.text,
    }));
  }
  return payload;
}

export function buildQuoteTooltipLines(quoteDraft) {
  const items = quoteDraft?.items || [];
  const textBudget = getTooltipTextBudget(items.length);
  return items.flatMap((item) => [item.sourceLabel, truncateQuoteText(item.text, textBudget)]);
}
