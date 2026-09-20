/* Author: donglixiao · Memory feed presentation, with delegated actions. */
import { icon } from './icons.js';
import { $, escapeHTML as e, dateLabel, titleOf, safeURL } from './utils.js';
import { state, filteredItems } from './store.js';
function card(item) {
  const name = titleOf(item),
    isVideo = item.kind === 'video';
  const thumbnail = item.thumbnail || (!isVideo ? item.url || `/media/${item.id}` : '');
  return `<article class="memory-card" data-id="${e(item.id)}"><header class="card-header"><div class="card-avatar">${icon(isVideo ? 'video' : 'image')}</div><div><span class="card-author">我们的家</span><span class="card-date">${e(dateLabel(item))}</span><div class="card-details">${icon(item.location ? 'pin' : 'leaf')}<span>${e(item.location || (item.dateSource === 'filename' && !item.title ? '从原片日期拾起的回忆' : '一家人的日常'))}</span></div></div><button class="icon-button" data-action="edit" aria-label="编辑${e(name)}" title="补充回忆">${icon('more')}</button></header><div class="card-content"><h3 class="card-title">${e(name)}</h3>${item.description ? `<p class="card-description">${e(item.description)}</p>` : ''}<button class="media-frame" data-action="open" aria-label="${isVideo ? '播放' : '查看'}${e(name)}">${thumbnail ? `<img src="${e(safeURL(thumbnail))}" alt="${e(name)}" loading="lazy" decoding="async">` : `<span class="media-fallback">${icon(isVideo ? 'video' : 'image')}<span>点开这段${isVideo ? '时光' : '回忆'}</span></span>`}${isVideo ? `<span class="play-circle">${icon('play')}</span>` : ''}<span class="media-kind">${icon(isVideo ? 'video' : 'image')}${isVideo ? '家庭影像' : '生活切片'}</span></button>${item.tags?.length ? `<div class="card-tags">${item.tags.map((tag) => `<button class="card-tag" data-action="tag" data-tag="${e(tag)}"># ${e(tag)}</button>`).join('')}</div>` : ''}<footer class="card-actions"><button class="card-action ${item.favorite ? 'favorited' : ''}" data-action="favorite" aria-pressed="${!!item.favorite}" aria-label="${item.favorite ? '取消珍藏' : '珍藏'}${e(name)}">${icon('heart')}<span>${item.favorite ? '已珍藏' : '珍藏'}</span></button><button class="card-action" data-action="edit">${icon('edit')}<span>补充回忆</span></button><button class="card-action" data-action="open" aria-label="放大查看${e(name)}">${icon('expand')}<span>放大看看</span></button></footer></div></article>`;
}
export function renderFeed() {
  const items = filteredItems(),
    feed = $('#feed');
  feed.classList.toggle('grid-view', state.grid);
  feed.setAttribute('aria-busy', 'false');
  $('#result-count').textContent = items.length;
  if (!items.length) {
    const filtered = state.query || state.year || state.location || state.tag;
    const messages = {
      photo: ['相片的位置，给美好留着', '把照片放进素材目录，刷新回忆库后就会出现在这里。'],
      favorites: ['把舍不得的瞬间，珍藏起来', '轻点回忆下的爱心，下次想念时就能更快找到。'],
      undated: ['每段回忆，都找到了日期', '所有回忆已有拍摄日期，继续去看看那些好时光吧。'],
    };
    const [title, description] = filtered
      ? ['还没找到这个瞬间', '试试其他关键词，或者清除筛选再看看。']
      : messages[state.view === 'all' ? state.type : state.view] || [
          '时光簿，等你来填满',
          '把视频或照片放进素材目录，再到管理回忆库中刷新。',
        ];
    feed.innerHTML = `<div class="empty-state">${icon(filtered ? 'search' : 'leaf')}<h3>${title}</h3><p>${description}</p><button class="secondary-button" data-action="reset">看看所有回忆</button></div>`;
  } else feed.innerHTML = items.slice(0, state.limit).map(card).join('');
  $('#load-more').hidden = items.length <= state.limit;
  $('#feed-end').hidden = !items.length || items.length > state.limit;
  const chips = [
    ['year', state.year === 'unknown' ? '日期待补充' : state.year],
    ['location', state.location],
    ['tag', state.tag],
  ];
  $('#active-filters').innerHTML = chips
    .filter(([, value]) => value)
    .map(([key, value]) => `<button class="filter-chip" data-clear="${key}">${e(value)} ×</button>`)
    .join('');
  $('#filter-dot').hidden = !chips.some(([, value]) => value);
  feed.querySelectorAll('img').forEach((img) =>
    img.addEventListener(
      'error',
      () => {
        const fallback = document.createElement('span');
        fallback.className = 'media-fallback';
        fallback.innerHTML = `${icon('image')}<span>预览暂不可用，点击打开原片</span>`;
        img.replaceWith(fallback);
      },
      { once: true },
    ),
  );
}
