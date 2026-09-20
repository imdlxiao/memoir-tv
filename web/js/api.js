/* Author: donglixiao · Library API and static-site local edit adapter. */
import { validCoordinates } from './geo.js';
const STORAGE_KEY = `memoir-edits-v1:${location.pathname}`;
let mode = 'library';
let currentCatalog = [];
let catalogCache = null;
let catalogETag = '';
async function request(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      message = (await response.json()).error || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
function localEdits() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    throw new Error('浏览器保存记录无法读取，请检查浏览器存储');
  }
}
async function requestCatalog(path, background) {
  const response = await fetch(path + (background ? '?background=1' : ''), {
    headers: catalogETag ? { 'If-None-Match': catalogETag } : {},
    cache: 'no-cache',
  });
  if (response.status === 304 && catalogCache) return { ...catalogCache, unchanged: true };
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(value.error || `读取回忆失败 (${response.status})`);
  }
  const nextTag = response.headers.get('ETag') || '';
  // Browsers may expose a revalidated cached response as 200 instead of 304.
  if (catalogCache && nextTag && nextTag === catalogETag)
    return { ...catalogCache, unchanged: true };
  const value = await response.json();
  catalogETag = nextTag;
  // Keep the raw snapshot separate from browser-only annotations in static mode.
  catalogCache = value;
  return { ...value, unchanged: false };
}
export async function loadCatalog(background = false) {
  let catalog;
  try {
    catalog = await requestCatalog('./data/catalog.json', background);
    mode = catalog.mode === 'library' ? 'library' : 'static';
  } catch {
    catalog = await requestCatalog('/api/catalog', background);
    mode = 'library';
  }
  if (!Array.isArray(catalog.items)) throw new Error('回忆索引格式不正确');
  if (mode === 'static') {
    const edits = localEdits();
    catalog.items = catalog.items.map((item) => ({ ...item, ...edits[item.id] }));
  }
  currentCatalog = catalog.items;
  return { ...catalog, mode, revision: catalogETag };
}
export function getMode() {
  return mode;
}
export async function saveMemory(id, changes) {
  validateBackup({ version: 1, memories: { [id]: changes } });
  if (mode === 'library')
    return request(`/api/memories/${encodeURIComponent(id)}`, 'PATCH', changes);
  const edits = localEdits();
  edits[id] = { ...edits[id], ...changes };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(edits));
}
export async function backup() {
  if (mode === 'library') return request('/api/backup');
  const keys = [
    'title',
    'description',
    'date',
    'precision',
    'location',
    'tags',
    'favorite',
    'coordinates',
  ];
  const memories = Object.fromEntries(
    currentCatalog.map((item) => [
      item.id,
      Object.fromEntries(keys.filter((key) => key in item).map((key) => [key, item[key]])),
    ]),
  );
  for (const [id, edit] of Object.entries(localEdits()))
    memories[id] = { ...memories[id], ...edit };
  return { version: 1, memories };
}
export async function saveBatch(ids, changes, tagMode = 'append') {
  ids = [...new Set(ids)];
  if (!ids.length || ids.length > 200) throw new Error('每次请选择 1 至 200 条回忆');
  if (!['append', 'replace', 'remove'].includes(tagMode)) throw new Error('标签操作不正确');
  if (
    !Object.keys(changes).length ||
    Object.keys(changes).some(
      (key) => !['date', 'precision', 'location', 'tags', 'favorite'].includes(key),
    )
  )
    throw new Error('请选择要修改的字段');
  if (mode === 'library') return request('/api/batch', 'POST', { ids, changes, tagMode });
  const edits = localEdits(),
    updates = {};
  for (const id of ids) {
    const item = currentCatalog.find((item) => item.id === id);
    if (!item) throw new Error('部分回忆已不在列表，请刷新后重试');
    const patch = { ...changes };
    if ('tags' in patch) {
      const existing = edits[id]?.tags || item.tags || [];
      if (tagMode === 'append') patch.tags = [...new Set([...existing, ...patch.tags])];
      if (tagMode === 'remove') patch.tags = existing.filter((tag) => !patch.tags.includes(tag));
    }
    updates[id] = patch;
  }
  validateBackup({ version: 1, memories: updates });
  for (const [id, patch] of Object.entries(updates)) edits[id] = { ...edits[id], ...patch };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(edits));
  return { count: ids.length };
}
function validateBackup(value) {
  if (
    value?.version !== 1 ||
    !value.memories ||
    typeof value.memories !== 'object' ||
    Array.isArray(value.memories)
  )
    throw new Error('不是有效的 memoir-tv 备份文件');
  const allowed = new Set([
    'title',
    'description',
    'date',
    'precision',
    'location',
    'tags',
    'favorite',
    'coordinates',
  ]);
  for (const [id, edit] of Object.entries(value.memories)) {
    if (
      edit &&
      'coordinates' in Object(edit) &&
      edit.coordinates !== null &&
      !validCoordinates(edit.coordinates)
    )
      throw new Error('地图坐标无效，请使用 WGS84 纬度和经度');
    if (
      !/^[a-f0-9]{20}$/.test(id) ||
      !edit ||
      typeof edit !== 'object' ||
      Array.isArray(edit) ||
      Object.keys(edit).some((key) => !allowed.has(key))
    )
      throw new Error('备份包含无效字段');
    for (const [key, limit] of [
      ['title', 120],
      ['description', 3000],
      ['location', 100],
      ['date', 10],
    ])
      if (key in edit && (typeof edit[key] !== 'string' || edit[key].length > limit))
        throw new Error('备份内容格式错误');
    if ('favorite' in edit && typeof edit.favorite !== 'boolean') throw new Error('珍藏状态无效');
    if (
      'tags' in edit &&
      (!Array.isArray(edit.tags) ||
        edit.tags.length > 20 ||
        edit.tags.some((t) => typeof t !== 'string' || t.length > 30))
    )
      throw new Error('标签格式无效');
    if ('precision' in edit && !['day', 'month', 'unknown'].includes(edit.precision))
      throw new Error('日期精度无效');
    if ('date' in edit || 'precision' in edit) {
      const precision = edit.precision || 'unknown';
      const value = edit.date || '';
      if (precision === 'unknown') {
        if (value) throw new Error('未知日期不能包含具体时间');
      } else {
        const pattern = precision === 'month' ? /^\d{4}-\d{2}$/ : /^\d{4}-\d{2}-\d{2}$/;
        const full = precision === 'month' ? value + '-01' : value;
        const parsed = new Date(full + 'T12:00:00Z');
        if (
          !pattern.test(value) ||
          Number(value.slice(0, 4)) < 1 ||
          Number.isNaN(parsed.valueOf()) ||
          parsed.toISOString().slice(0, 10) !== full
        )
          throw new Error('拍摄日期不存在或精度不匹配');
      }
    }
  }
}
export async function importBackup(value) {
  validateBackup(value);
  if (mode === 'library') return request('/api/import', 'POST', value);
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...localEdits(), ...value.memories }));
}
export const startScan = () => request('/api/scan', 'POST', {});
export const scanStatus = () => request('/api/status');
