/* Author: donglixiao · Framework-independent catalog queries. */
export const state = {
  items: [],
  mode: 'library',
  view: 'all',
  type: 'all',
  query: '',
  year: '',
  month: '',
  location: '',
  tag: '',
  ascending: false,
  limit: 12,
  grid: false,
  selecting: false,
  selected: new Set(),
};
export function filteredItems() {
  const query = state.query.trim().toLocaleLowerCase();
  return state.items
    .filter((item) => {
      if (state.view === 'favorites' && !item.favorite) return false;
      if (state.view === 'undated' && item.date) return false;
      if (['video', 'photo'].includes(state.view) && item.kind !== state.view) return false;
      if (state.type !== 'all' && item.kind !== state.type) return false;
      if (
        state.year &&
        (state.year === 'unknown' ? !!item.date : !item.date?.startsWith(state.year))
      )
        return false;
      if (state.location && item.location !== state.location) return false;
      if (state.month && item.date?.slice(5, 7) !== state.month) return false;
      if (state.tag && !(item.tags || []).includes(state.tag)) return false;
      return (
        !query ||
        [
          item.title,
          item.description,
          item.filename,
          item.location,
          item.date,
          ...(item.tags || []),
        ]
          .join(' ')
          .toLocaleLowerCase()
          .includes(query)
      );
    })
    .sort((a, b) => {
      if (!a.date && b.date) return 1;
      if (a.date && !b.date) return -1;
      const comparison =
        (a.date || '').localeCompare(b.date || '') || a.filename.localeCompare(b.filename);
      return state.ascending ? comparison : -comparison;
    });
}
export function counts(field) {
  const values = new Map();
  for (const item of state.items) {
    const entries =
      field === 'year'
        ? [item.date?.slice(0, 4) || 'unknown']
        : field === 'tags'
          ? item.tags || []
          : [item[field]];
    for (const value of entries.filter(Boolean)) values.set(value, (values.get(value) || 0) + 1);
  }
  return [...values.entries()].sort((a, b) => b[1] - a[1]);
}
