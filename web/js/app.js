/* Author: donglixiao · Application composition and event coordination. */
import { hydrateIcons, icon } from './icons.js';
import { $, escapeHTML as e, toast, setupDialog } from './utils.js';
import { loadCatalog, saveMemory } from './api.js';
import { state, filteredItems, counts } from './store.js';
import { renderFeed } from './feed.js';
import { editMemory } from './editor.js';
import { openViewer, initializeViewer } from './viewer.js';
import { openLibrary } from './library.js';
import { setTV, initializeTV } from './tv.js';
import { startLibrarySync } from './sync.js';
import { initializeBatch, toggleSelection } from './batch.js';
import { initializeDiscovery, updateDiscovery } from './discovery.js';
import { preferences, savePreference } from './preferences.js';
import { openMap } from './map.js';

const viewNames = {
  all: '所有回忆',
  video: '家庭影像',
  photo: '相片集',
  favorites: '我的珍藏',
  undated: '待补日期',
};
const savedPreferences = preferences();
state.grid = savedPreferences.grid;
state.ascending = savedPreferences.ascending;
function renderOverview() {
  $('#nav-count').textContent = state.items.length;
  $('#undated-count').textContent = state.items.filter((i) => !i.date).length;
  $('#video-count').textContent = state.items.filter((i) => i.kind === 'video').length;
  $('#photo-count').textContent = state.items.filter((i) => i.kind === 'photo').length;
  $('#favorite-count').textContent = state.items.filter((i) => i.favorite).length;
  const years = counts('year').sort((a, b) => b[0].localeCompare(a[0])),
    places = counts('location'),
    tags = counts('tags');
  $('#year-list').innerHTML = years
    .map(
      ([year, count]) =>
        `<button class="year-button" data-year="${e(year)}"><span>${year === 'unknown' ? '日期待补' : e(year)}</span><span class="year-bar"><i style="width:${(count / Math.max(state.items.length, 1)) * 100}%"></i></span><small>${count}</small></button>`,
    )
    .join('');
  $('#places-list').innerHTML = places.length
    ? places
        .slice(0, 6)
        .map(
          ([place, count]) =>
            `<button class="place-button" data-location="${e(place)}"><span>${icon('pin')}</span><span>${e(place)}</span><small>${count} 段回忆</small></button>`,
        )
        .join('')
    : '<p class="sidebar-empty">故事发生在哪里？<br>为回忆补充地点，就能从这里出发。</p>';
  $('#tags-list').innerHTML = tags.length
    ? tags
        .slice(0, 16)
        .map(([tag]) => `<button data-tag="${e(tag)}"># ${e(tag)}</button>`)
        .join('')
    : '<p class="sidebar-empty">给回忆一个小主题，<br>下次想念时，更容易找到。</p>';
  for (const [selector, values, field, label] of [
    ['#year-filter', years, 'year', '所有年份'],
    [
      '#month-filter',
      Array.from({ length: 12 }, (_, i) => [
        String(i + 1).padStart(2, '0'),
        state.items.filter((item) => item.date?.slice(5, 7) === String(i + 1).padStart(2, '0'))
          .length,
      ]).filter(([, count]) => count),
      'month',
      '所有月份',
    ],
    ['#location-filter', places, 'location', '所有地点'],
    ['#tag-filter', tags, 'tag', '所有标签'],
  ]) {
    $(selector).innerHTML =
      `<option value="">${label}</option>` +
      values
        .map(
          ([value, count]) =>
            `<option value="${e(value)}">${e(value === 'unknown' ? '日期待补充' : field === 'month' ? Number(value) + ' 月' : value)} (${count})</option>`,
        )
        .join('');
    $(selector).value = state[field];
  }
  let datalist = $('#known-places');
  if (!datalist) {
    datalist = document.createElement('datalist');
    datalist.id = 'known-places';
    document.body.append(datalist);
  }
  datalist.innerHTML = places.map(([place]) => `<option value="${e(place)}"></option>`).join('');
}
function render() {
  renderOverview();
  renderFeed();
  updateDiscovery();
}
async function refresh(background = false) {
  const catalog = await loadCatalog();
  if (
    background &&
    (document.querySelector('dialog[open]') ||
      JSON.stringify(catalog.items) === JSON.stringify(state.items))
  )
    return catalog;
  state.items = catalog.items;
  state.mode = catalog.mode;
  render();
  return catalog;
}
function resetFilters() {
  state.query = '';
  state.year = '';
  state.month = '';
  state.location = '';
  state.tag = '';
  state.type = 'all';
  $('#search').value = '';
  state.limit = 12;
}
function switchView(view) {
  state.view = view;
  resetFilters();
  $('#page-name').textContent = viewNames[view];
  $('#feed-title').innerHTML =
    `${view === 'all' ? '每一刻，都算数' : viewNames[view]} <span id="result-count"></span>`;
  $('#feed-subtitle').textContent = {
    all: '沿着时间，重逢那些小美好',
    video: '声音与画面，让那一刻重新鲜活',
    photo: '一张相片，装得下一整个故事',
    favorites: '那些想要一看再看的瞬间',
    undated: '慢慢想起，给每段时光一个位置',
  }[view];
  document
    .querySelectorAll('[data-view]')
    .forEach((el) => el.classList.toggle('active', el.dataset.view === view));
  document
    .querySelectorAll('[data-mobile-view]')
    .forEach((el) => el.classList.toggle('active', el.dataset.mobileView === view));
  document
    .querySelectorAll('[data-tab]')
    .forEach((el) => el.setAttribute('aria-selected', el.dataset.tab === 'all'));
  render();
}
function filter(field, value) {
  state[field] = value;
  state.limit = 12;
  render();
}
function library() {
  openLibrary(state.items, refresh, () => setTV(true));
}

hydrateIcons();
document.querySelectorAll('dialog').forEach(setupDialog);
initializeViewer();
initializeTV();
initializeBatch(renderFeed, refresh);
initializeDiscovery();
const editFromMap = (item) =>
  editMemory(item, () => refresh().catch((error) => toast(error.message)));
const atlas = (focusId) =>
  openMap(focusId ? state.items : filteredItems(), {
    focusId,
    onOpen: openViewer,
    onEdit: editFromMap,
  });
$('#map-button').onclick = () => atlas();
$('#map-shortcut').onclick = () => atlas();
document.addEventListener('memoir:map', (event) => atlas(event.detail));
document.addEventListener('memoir:edit', (event) => {
  const item = state.items.find((item) => item.id === event.detail);
  if (item) editFromMap(item);
});
$('#viewer-dialog').addEventListener('close', render);
const now = new Date();
$('#today-date').innerHTML =
  `${String(now.getMonth() + 1).padStart(2, '0')}<span style="opacity:.4"> / </span>${String(now.getDate()).padStart(2, '0')}<small>${['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][now.getDay()]}</small>`;
try {
  document.documentElement.dataset.theme = localStorage.getItem('memoir-theme') || 'light';
} catch {}
$('#theme-button').onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem('memoir-theme', theme);
  } catch {}
  $('#theme-button').setAttribute('aria-label', theme === 'dark' ? '切换浅色模式' : '切换深色模式');
};
$('#navigation').onclick = (event) => {
  const button = event.target.closest('[data-view]');
  if (button) switchView(button.dataset.view);
};
$('.mobile-nav').onclick = (event) => {
  const button = event.target.closest('[data-mobile-view]');
  if (button) {
    switchView(button.dataset.mobileView);
    window.scrollTo({ top: 0 });
  }
};
$('#library-button').onclick = library;
$('#mobile-library').onclick = library;
$('#tv-button').onclick = () => setTV(true);
let searchTimer;
$('#search').addEventListener('input', (event) => {
  clearTimeout(searchTimer);
  const value = event.target.value;
  searchTimer = setTimeout(() => filter('query', value), 180);
});
$('#filter-toggle').onclick = () => {
  const panel = $('#filter-panel');
  panel.hidden = !panel.hidden;
  $('#filter-toggle').setAttribute('aria-expanded', !panel.hidden);
};
for (const [selector, field] of [
  ['#year-filter', 'year'],
  ['#month-filter', 'month'],
  ['#location-filter', 'location'],
  ['#tag-filter', 'tag'],
])
  $(selector).onchange = (event) => filter(field, event.target.value);
$('#reset-filters').onclick = () => {
  resetFilters();
  render();
  document
    .querySelectorAll('[data-tab]')
    .forEach((el) => el.setAttribute('aria-selected', el.dataset.tab === 'all'));
};
$('#sort-button').onclick = () => {
  state.ascending = !state.ascending;
  savePreference('ascending', state.ascending);
  $('#sort-button').innerHTML =
    `${icon('sort')}<span>${state.ascending ? '从旧到新' : '从新到旧'}</span>`;
  renderFeed();
};
$('.feed-tabs').onclick = (event) => {
  const button = event.target.closest('[data-tab]');
  if (!button) return;
  state.type = button.dataset.tab;
  state.limit = 12;
  if (['photo', 'video'].includes(state.view) && state.type !== state.view) {
    state.view = 'all';
    $('#page-name').textContent = viewNames.all;
    document
      .querySelectorAll('[data-view],[data-mobile-view]')
      .forEach((el) =>
        el.classList.toggle('active', (el.dataset.view || el.dataset.mobileView) === 'all'),
      );
    $('#feed-title').innerHTML = '每一刻，都算数 <span id="result-count"></span>';
    $('#feed-subtitle').textContent = '沿着时间，重逢那些小美好';
  }
  document
    .querySelectorAll('[data-tab]')
    .forEach((el) => el.setAttribute('aria-selected', el === button));
  renderFeed();
};
function setGrid(grid) {
  state.grid = grid;
  savePreference('grid', grid);
  $('#grid-view').classList.toggle('active', grid);
  $('#list-view').classList.toggle('active', !grid);
  $('#grid-view').setAttribute('aria-pressed', grid);
  $('#list-view').setAttribute('aria-pressed', !grid);
  renderFeed();
}
$('#grid-view').onclick = () => setGrid(true);
$('#list-view').onclick = () => setGrid(false);
$('#grid-view').classList.toggle('active', state.grid);
$('#list-view').classList.toggle('active', !state.grid);
$('#grid-view').setAttribute('aria-pressed', state.grid);
$('#list-view').setAttribute('aria-pressed', !state.grid);
$('#sort-button').innerHTML =
  `${icon('sort')}<span>${state.ascending ? '从旧到新' : '从新到旧'}</span>`;
$('#load-more').onclick = () => {
  const firstNew = state.limit;
  state.limit += 12;
  renderFeed();
  $('#feed').children[firstNew]?.querySelector('button')?.focus({ preventScroll: true });
};
$('#active-filters').onclick = (event) => {
  const button = event.target.closest('[data-clear]');
  if (button) filter(button.dataset.clear, '');
};
$('#year-list').onclick = (event) => {
  const button = event.target.closest('[data-year]');
  if (button) filter('year', button.dataset.year);
};
$('#places-list').onclick = (event) => {
  const button = event.target.closest('[data-location]');
  if (button) filter('location', button.dataset.location);
};
$('#tags-list').onclick = (event) => {
  const button = event.target.closest('[data-tag]');
  if (button) filter('tag', button.dataset.tag);
};
$('#feed').onclick = async (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  if (button.dataset.action === 'reset') {
    switchView('all');
    return;
  }
  const item = state.items.find((i) => i.id === button.closest('[data-id]')?.dataset.id);
  if (!item) return;
  if (button.dataset.action === 'select' || (state.selecting && button.dataset.action === 'open')) {
    toggleSelection(item.id, renderFeed);
    return;
  }
  if (button.dataset.action === 'open') openViewer(filteredItems(), item.id);
  if (button.dataset.action === 'edit')
    editMemory(item, () => refresh().catch((error) => toast(error.message)));
  if (button.dataset.action === 'tag') filter('tag', button.dataset.tag);
  if (button.dataset.action === 'favorite') {
    button.disabled = true;
    try {
      const favorite = !item.favorite;
      await saveMemory(item.id, { favorite });
      item.favorite = favorite;
      render();
      $(`[data-id="${item.id}"] [data-action="favorite"]`)?.focus({ preventScroll: true });
      toast(favorite ? '放进珍藏，留给以后的想念' : '已取消珍藏');
    } catch (error) {
      button.disabled = false;
      toast(error.message);
    }
  }
};
document.addEventListener('keydown', (event) => {
  if (
    event.key === '/' &&
    !document.querySelector('dialog[open]') &&
    !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)
  ) {
    event.preventDefault();
    $('#search').focus();
  }
});
refresh()
  .then(() => {
    if (state.mode === 'library') startLibrarySync(() => refresh(true));
  })
  .catch((error) => {
    $('#feed').setAttribute('aria-busy', 'false');
    $('#feed').innerHTML =
      `<div class="empty-state">${icon('folder')}<h3>时光簿还没有打开</h3><p>${e(error.message)}。请确认回忆库服务已启动，然后刷新页面。</p><button class="secondary-button" id="retry-load">重新打开</button></div>`;
    $('#retry-load').onclick = () => location.reload();
  });
