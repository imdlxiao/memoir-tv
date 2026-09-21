/* Author: donglixiao · Resume playback, photo slideshows, and original media inspection. */
import { icon } from './icons.js';
import {
  $,
  escapeHTML as e,
  titleOf,
  dateLabel,
  mediaURL,
  safeURL,
  fileSize,
  openDialog,
  toast,
} from './utils.js';
import { attachProgress, clockLabel } from './progress.js';
import { preferences, savePreference } from './preferences.js';
import { captureHTML } from './capture.js';
import { validCoordinates } from './geo.js';
import { canEdit } from './account.js';

let playlist = [],
  index = 0,
  slideshow = null,
  detachProgress = null,
  continuous = false,
  interval = 8,
  speed = 1;
function stopSlideshow() {
  clearTimeout(slideshow);
  slideshow = null;
}
function releaseVideo() {
  detachProgress?.();
  detachProgress = null;
  const video = $('video', $('#viewer-dialog'));
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
}
function schedulePhoto() {
  stopSlideshow();
  const dialog = $('#viewer-dialog'),
    image = $('.viewer-media img', dialog);
  if (
    dialog.open &&
    continuous &&
    !document.hidden &&
    !$('.viewer-media', dialog).classList.contains('zoomed') &&
    image?.complete &&
    image.naturalWidth &&
    index < playlist.length - 1
  )
    slideshow = setTimeout(() => navigate(1), interval * 1000);
}
function playVideo() {
  $('video', $('#viewer-dialog'))
    ?.play()
    .catch(() => {});
}
function render() {
  stopSlideshow();
  releaseVideo();
  const dialog = $('#viewer-dialog'),
    item = playlist[index],
    video = item.kind === 'video';
  dialog.innerHTML = `<header class="viewer-toolbar"><div><h2>${e(titleOf(item))}</h2><p>${e(dateLabel(item))}${item.location ? ' · ' + e(item.location) : ''}</p></div><div class="viewer-tools"><button class="icon-button" data-fullscreen aria-label="全屏播放">${icon('expand')}</button><button class="icon-button" data-close aria-label="关闭放映室">${icon('close')}</button></div></header>
    <div class="resume-notice" hidden><span></span><button data-restart>从头看</button></div>
    <div class="viewer-media">${video ? `<video controls playsinline preload="metadata" src="${e(mediaURL(item))}" ${item.thumbnail ? `poster="${e(safeURL(item.thumbnail))}"` : ''}></video>` : `<img src="${e(mediaURL(item))}" alt="${e(titleOf(item))}">`}</div>
    <div class="viewer-options"><button data-continuous aria-pressed="${continuous}">${continuous ? '暂停连播' : '连续播放'}</button>${video ? `<label>速度<select data-speed aria-label="播放速度">${[0.5, 0.75, 1, 1.25, 1.5, 2].map((value) => `<option value="${value}" ${value === speed ? 'selected' : ''}>${value}×</option>`).join('')}</select></label><button data-loop aria-pressed="false">循环本段</button>` : `<label>每张停留<select data-interval aria-label="照片停留时间">${[5, 8, 15, 30].map((value) => `<option value="${value}" ${value === interval ? 'selected' : ''}>${value} 秒</option>`).join('')}</select></label><button data-zoom aria-pressed="false">查看原始尺寸</button>`}<span class="playback-note">${video ? '自动记住进度 · 仅此浏览器' : '点击照片可放大，再点还原'}</span></div>
    <footer class="viewer-footer"><button data-previous ${index === 0 ? 'disabled' : ''}>${icon('left')}上一段</button><span>${index + 1} / ${playlist.length}<span class="viewer-hint"> · ← → 切换 · Esc 返回</span></span><button data-next ${index === playlist.length - 1 ? 'disabled' : ''}>下一段${icon('right')}</button></footer>
    <details class="viewer-details"><summary>原片信息与下载</summary><dl><dt>文件名</dt><dd>${e(item.filename)}</dd><dt>原片大小</dt><dd>${fileSize(item.size || 0)}</dd><dt>拍摄时间</dt><dd>${e(dateLabel(item))}</dd><dt>地点</dt><dd>${e(item.location || '还没补充')}</dd>${item.tags?.length ? `<dt>标签</dt><dd>${item.tags.map((tag) => '#' + e(tag)).join(' · ')}</dd>` : ''}${item.description ? `<dt>故事</dt><dd>${e(item.description)}</dd>` : ''}</dl><a href="${e(mediaURL(item))}" download="${e(item.filename)}">${icon('download')}下载原片</a></details>`;
  $('[data-close]', dialog).onclick = () => dialog.close();
  const details = $('.viewer-details', dialog);
  details.insertAdjacentHTML('afterbegin', captureHTML(item));
  // Keep the summary first so the native disclosure remains keyboard accessible.
  details.prepend($('summary', details));
  $('[data-capture-map]', dialog).onclick = () => {
    if (!validCoordinates(item.coordinates) && !canEdit()) return toast('这条回忆尚未添加拍摄位置');
    dialog.close();
    document.dispatchEvent(
      new CustomEvent(validCoordinates(item.coordinates) ? 'memoir:map' : 'memoir:edit', {
        detail: item.id,
      }),
    );
  };
  $('[data-capture-edit]', dialog).onclick = () => {
    dialog.close();
    document.dispatchEvent(new CustomEvent('memoir:edit', { detail: item.id }));
  };
  $('[data-previous]', dialog).onclick = () => navigate(-1);
  $('[data-next]', dialog).onclick = () => navigate(1);
  $('[data-fullscreen]', dialog).onclick = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (dialog.requestFullscreen) await dialog.requestFullscreen();
      else if ($('video', dialog)?.webkitEnterFullscreen)
        $('video', dialog).webkitEnterFullscreen();
      else toast('当前浏览器不支持全屏，请使用播放器全屏按钮');
    } catch {
      toast('当前浏览器未允许全屏');
    }
  };
  $('[data-continuous]', dialog).onclick = (event) => {
    continuous = !continuous;
    savePreference('continuous', continuous);
    event.currentTarget.setAttribute('aria-pressed', continuous);
    event.currentTarget.textContent = continuous ? '暂停连播' : '连续播放';
    schedulePhoto();
  };
  const media = $('video,img', $('.viewer-media', dialog));
  media.addEventListener('error', () => {
    stopSlideshow();
    detachProgress?.();
    detachProgress = null;
    $('.viewer-media', dialog).innerHTML =
      `<div class="viewer-error"><p>这份原片暂时无法打开。查看权限可能已变更、文件已移出，或浏览器不支持该编码。请返回首页刷新；可见的原片也可下载后查看。</p><a href="${e(mediaURL(item))}" download="${e(item.filename)}">下载原片</a></div>`;
  });
  if (video) {
    media.playbackRate = speed;
    detachProgress = attachProgress(media, item, (time) => {
      const notice = $('.resume-notice', dialog);
      notice.hidden = false;
      $('span', notice).textContent = `接着上次的 ${clockLabel(time)} 继续看`;
    });
    $('[data-restart]', dialog).onclick = () => {
      media.currentTime = 0;
      $('.resume-notice', dialog).hidden = true;
      playVideo();
    };
    $('[data-speed]', dialog).onchange = (event) => {
      speed = Number(event.target.value);
      media.playbackRate = speed;
      savePreference('speed', speed);
    };
    $('[data-loop]', dialog).onclick = (event) => {
      media.loop = !media.loop;
      event.currentTarget.setAttribute('aria-pressed', media.loop);
    };
    media.addEventListener('ended', () => {
      if (continuous) navigate(1);
    });
  } else {
    media.addEventListener('load', schedulePhoto);
    $('[data-interval]', dialog).onchange = (event) => {
      interval = Number(event.target.value);
      savePreference('interval', interval);
      schedulePhoto();
    };
    const zoom = () => {
      const enabled = $('.viewer-media', dialog).classList.toggle('zoomed');
      $('[data-zoom]', dialog).setAttribute('aria-pressed', enabled);
      $('[data-zoom]', dialog).textContent = enabled ? '适应屏幕' : '查看原始尺寸';
      if (enabled) stopSlideshow();
      else schedulePhoto();
    };
    media.onclick = zoom;
    $('[data-zoom]', dialog).onclick = zoom;
    schedulePhoto();
  }
  if (dialog.open)
    (index < playlist.length - 1 ? $('[data-next]', dialog) : $('[data-previous]', dialog)).focus({
      preventScroll: true,
    });
}
function navigate(delta) {
  const next = index + delta;
  if (next < 0 || next >= playlist.length) return;
  index = next;
  render();
  if (continuous) playVideo();
}
export function openViewer(items, id) {
  if (!items.length) return;
  playlist = items;
  index = Math.max(
    0,
    items.findIndex((item) => item.id === id),
  );
  const saved = preferences();
  speed = saved.speed;
  interval = saved.interval;
  continuous = document.body.classList.contains('tv-mode') || saved.continuous;
  render();
  openDialog($('#viewer-dialog'));
  playVideo();
  schedulePhoto();
}
export function initializeViewer() {
  const dialog = $('#viewer-dialog');
  dialog.addEventListener('close', () => {
    stopSlideshow();
    releaseVideo();
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  });
  dialog.addEventListener('keydown', (event) => {
    if (['VIDEO', 'SELECT', 'INPUT', 'TEXTAREA'].includes(event.target.tagName)) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      navigate(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopSlideshow();
    else schedulePhoto();
  });
}
