/* Author: donglixiao · Honest date-precision-aware anniversary discovery. */
import { $, escapeHTML as e, dateLabel, titleOf, openDialog, toast } from './utils.js';
import { icon } from './icons.js';
import { state, filteredItems } from './store.js';
import { openViewer } from './viewer.js';
import { readProgress } from './progress.js';

function unfinished() {
  return state.items
    .filter((item) => item.kind === 'video' && readProgress(item))
    .sort((a, b) => readProgress(b).updatedAt - readProgress(a).updatedAt);
}
export function updateDiscovery() {
  const items = unfinished();
  $('#resume-button').hidden = !items.length;
  $('#resume-button').innerHTML =
    `${icon('play')}接着看${items.length ? ' · ' + items.length : ''}`;
}

export function anniversaryGroups(items, now = new Date()) {
  const year = now.getFullYear(),
    month = String(now.getMonth() + 1).padStart(2, '0'),
    day = String(now.getDate()).padStart(2, '0');
  const historic = items.filter((item) => item.date && Number(item.date.slice(0, 4)) < year);
  return {
    today: historic.filter(
      (item) => item.precision === 'day' && item.date.slice(5) === `${month}-${day}`,
    ),
    month: historic.filter((item) => item.precision === 'month' && item.date.slice(5, 7) === month),
  };
}

export function initializeDiscovery() {
  $('#resume-button').onclick = () => {
    const items = unfinished();
    if (items.length) openViewer(items, items[0].id);
    else toast('暂时没有未看完的视频');
  };
  $('#random-button').onclick = () => {
    const items = filteredItems();
    if (!items.length) {
      toast('当前筛选下还没有回忆，清除筛选再试试');
      return;
    }
    const item = items[Math.floor(Math.random() * items.length)];
    openViewer(items, item.id);
  };
  $('#anniversary-button').onclick = () => {
    const dialog = $('#discovery-dialog'),
      groups = anniversaryGroups(state.items),
      items = [...groups.today, ...groups.month];
    const section = (heading, description, list) =>
      `<section class="anniversary-section"><h3>${heading} <span>${list.length}</span></h3><p>${description}</p>${list.length ? list.map((item) => `<button class="anniversary-memory" data-memory="${e(item.id)}"><span class="anniversary-year">${e(item.date.slice(0, 4))}</span><span><strong>${e(titleOf(item))}</strong><small>${e(dateLabel(item))}${item.location ? ' · ' + e(item.location) : ''}</small></span>${icon('right')}</button>`).join('') : '<div class="anniversary-empty">还没有对应的回忆。慢慢补充日期，以后的今天就能再相遇。</div>'}</section>`;
    dialog.innerHTML = `<header class="dialog-header"><div><h2>那年这时候，我们在一起</h2><p>日期精确到天和大约某月的回忆，分别重温。</p></div><button class="icon-button" data-close aria-label="关闭往年今日">${icon('close')}</button></header><div class="discovery-content">${section('往年今日', '发生在往年同一个月、同一天的故事。', groups.today)}${section('往年这个月 · 大约', '只记得到月份的回忆，不把它当成某一天。', groups.month)}</div>`;
    $('[data-close]', dialog).onclick = () => dialog.close();
    dialog.querySelectorAll('[data-memory]').forEach(
      (button) =>
        (button.onclick = () => {
          dialog.close();
          openViewer(items, button.dataset.memory);
        }),
    );
    openDialog(dialog);
  };
}
