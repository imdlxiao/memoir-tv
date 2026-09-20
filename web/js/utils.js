/* Author: donglixiao · Shared safe rendering and display utilities. */
export const $ = (selector, root = document) => root.querySelector(selector);
export const escapeHTML = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
export function dateLabel(item) {
  if (!item.date || item.precision === 'unknown') return '日期待补充';
  const [year, month, day] = item.date.split('-').map(Number);
  return `${year} 年 ${month} 月${item.precision === 'day' ? ` ${day} 日` : ' · 大约'}`;
}
export function titleOf(item) {
  return (
    item.title ||
    (item.date
      ? `${Number(item.date.slice(5, 7))} 月的一段${item.kind === 'photo' ? '光影' : '时光'}`
      : '还没命名的回忆')
  );
}
export function mediaURL(item) {
  return safeURL(item.url || `/media/${encodeURIComponent(item.id)}`);
}
export function safeURL(value) {
  try {
    const url = new URL(value, location.href);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}
export function fileSize(value) {
  return value >= 1073741824
    ? `${(value / 1073741824).toFixed(1)} GB`
    : `${(value / 1048576).toFixed(1)} MB`;
}
let toastTimer;
export function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3800);
}
export function downloadJSON(value, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function openDialog(dialog) {
  dialog.showModal();
  document.body.style.overflow = 'hidden';
}
export function setupDialog(dialog) {
  dialog.addEventListener('close', () => {
    if (!document.querySelector('dialog[open]')) document.body.style.overflow = '';
  });
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        dialog.close();
    }
  });
}
