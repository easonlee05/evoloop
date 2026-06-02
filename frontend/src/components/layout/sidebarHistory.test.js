import test from 'node:test';
import assert from 'node:assert/strict';
import { flattenConversationGroups } from './sidebarHistory.js';

test('flattenConversationGroups keeps chronological section order without extra footer row', () => {
  const items = flattenConversationGroups({
    today: [{ id: 't1', label: '今天任务', time: '10:00' }],
    yesterday: [{ id: 'y1', label: '昨天任务', time: '09:00' }],
    older: [{ id: 'o1', label: '更早任务', time: '08:00' }],
  });

  assert.deepEqual(items, [
    { type: 'group', label: '今天' },
    { type: 'item', id: 't1', label: '今天任务', time: '10:00' },
    { type: 'group', label: '昨天' },
    { type: 'item', id: 'y1', label: '昨天任务', time: '09:00' },
    { type: 'group', label: '更早' },
    { type: 'item', id: 'o1', label: '更早任务', time: '08:00' },
  ]);
});
