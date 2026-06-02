export function flattenConversationGroups({ today = [], yesterday = [], older = [] }) {
  const sections = [
    { label: '今天', items: today },
    { label: '昨天', items: yesterday },
    { label: '更早', items: older },
  ];

  return sections.flatMap(({ label, items }) => {
    if (!items.length) return [];
    return [{ type: 'group', label }, ...items.map((item) => ({ type: 'item', ...item }))];
  });
}
