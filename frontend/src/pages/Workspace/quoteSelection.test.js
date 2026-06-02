import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildQuoteDraft,
  summarizeQuoteDraft,
  appendQuoteDraft,
  clearQuoteDraft,
  buildDecisionPayload,
  buildQuoteTooltipLines,
  getQuoteTooltipLineClamp,
} from './quoteSelection.js';

test('appendQuoteDraft aggregates multiple selections into one draft', () => {
  const first = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'First line',
  });
  const second = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: 'Second line',
  });

  const combined = appendQuoteDraft(null, first);
  const updated = appendQuoteDraft(combined, second);

  assert.equal(updated.items.length, 2);
  assert.equal(updated.items[0].text, 'First line');
  assert.equal(updated.items[1].sourceType, 'editor');
  assert.equal(summarizeQuoteDraft(updated), '2 个已选文本片段');
});

test('appendQuoteDraft ignores duplicate source and text pairs', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'Repeated',
  });

  const combined = appendQuoteDraft(null, item);
  const duplicated = appendQuoteDraft(combined, item);

  assert.equal(duplicated.items.length, 1);
  assert.equal(summarizeQuoteDraft(duplicated), '1 个已选文本片段');
});

test('clearQuoteDraft resets the draft state', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'Repeated',
  });

  assert.equal(clearQuoteDraft(appendQuoteDraft(null, item)), null);
});

test('buildDecisionPayload includes quoted selections only when present', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'A selected paragraph',
  });

  const payload = buildDecisionPayload('继续改这个点', appendQuoteDraft(null, item));

  assert.equal(payload.decision, '继续改这个点');
  assert.equal(payload.quoted_selections.length, 1);
  assert.deepEqual(payload.quoted_selections[0], {
    source_type: 'message',
    source_id: 'msg_1',
    source_label: 'PM Agent',
    text: 'A selected paragraph',
  });

  const plainPayload = buildDecisionPayload('纯文本消息', null);
  assert.equal('quoted_selections' in plainPayload, false);
});

test('buildQuoteTooltipLines formats source-aware preview text', () => {
  const first = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: '第一段引用内容',
  });
  const second = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: '第二段引用内容',
  });

  const lines = buildQuoteTooltipLines(appendQuoteDraft(appendQuoteDraft(null, first), second));

  assert.deepEqual(lines, [
    'PM Agent',
    '第一段引用内容',
    '文档编辑区',
    '第二段引用内容',
  ]);
});

test('buildQuoteTooltipLines truncates long quote text to 150 chars', () => {
  const item = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_2',
    sourceLabel: 'QA Agent',
    text: 'a'.repeat(180),
  });

  const lines = buildQuoteTooltipLines(appendQuoteDraft(null, item));

  assert.equal(lines[0], 'QA Agent');
  assert.equal(lines[1].length, 151);
  assert.equal(lines[1].endsWith('…'), true);
});

test('buildQuoteTooltipLines shortens each segment when there are more quoted items', () => {
  const item1 = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_1',
    sourceLabel: 'PM Agent',
    text: 'a'.repeat(180),
  });
  const item2 = buildQuoteDraft({
    sourceType: 'message',
    sourceId: 'msg_2',
    sourceLabel: 'QA Agent',
    text: 'b'.repeat(180),
  });
  const item3 = buildQuoteDraft({
    sourceType: 'editor',
    sourceId: 'editor',
    sourceLabel: '文档编辑区',
    text: 'c'.repeat(180),
  });

  const singleLines = buildQuoteTooltipLines(appendQuoteDraft(null, item1));
  const tripleDraft = appendQuoteDraft(appendQuoteDraft(appendQuoteDraft(null, item1), item2), item3);
  const tripleLines = buildQuoteTooltipLines(tripleDraft);

  assert.equal(singleLines[1].length, 151);
  assert.equal(tripleLines[1].length < singleLines[1].length, true);
  assert.equal(tripleLines[3].length, tripleLines[1].length);
  assert.equal(tripleLines[5].length, tripleLines[1].length);
});

test('getQuoteTooltipLineClamp reduces lines as item count grows', () => {
  assert.equal(getQuoteTooltipLineClamp(1), 5);
  assert.equal(getQuoteTooltipLineClamp(2), 3);
  assert.equal(getQuoteTooltipLineClamp(3), 2);
  assert.equal(getQuoteTooltipLineClamp(6), 2);
});
