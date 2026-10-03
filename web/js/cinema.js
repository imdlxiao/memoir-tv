/* Author: donglixiao · Immersive playback layout and remote control lifecycle. */
import { clockLabel } from './progress.js';
import { enableRemote, isRemote, setPlayerRemote } from './remote.js';
import { toast } from './utils.js';

export function attachCinema(dialog, stage, saved = {}) {
  const media = stage.querySelector('video,img');
  const video = media?.tagName === 'VIDEO' ? media : null;
  const originalControls = video?.controls;
  const remoteBefore = isRemote();
  const moves = [];
  let active = false,
    timer = null,
    controls = null,
    panel = null,
    pageFullscreen = saved.pageFullscreen || false;
  let seenFullscreen = !!fullscreen(),
    disposed = false;
  function fullscreen() {
    return document.fullscreenElement || document.webkitFullscreenElement;
  }
  function move(node, destination) {
    if (!node) return;
    const anchor = document.createComment('cinema origin');
    node.before(anchor);
    moves.push([node, anchor]);
    destination.append(node);
  }
  function primary() {
    return (
      controls?.querySelector('[data-remote-play]') ||
      controls?.querySelector('button:not(:disabled)')
    );
  }
  function arm() {
    clearTimeout(timer);
    if (
      !active ||
      !panel.hidden ||
      (video && (video.paused || video.readyState < 2 || video.seeking || video.error))
    )
      return;
    timer = setTimeout(() => {
      if (!dialog.open || !panel.hidden || (video && video.paused)) return;
      stage.classList.add('cinema-idle');
      stage.focus({ preventScroll: true });
    }, 4000);
  }
  function show(focus = false) {
    if (!active) return;
    stage.classList.remove('cinema-idle');
    if (focus) primary()?.focus({ preventScroll: true });
    arm();
  }
  function closePanel() {
    panel.hidden = true;
    stage.classList.remove('cinema-panel-open');
    stage.querySelector('[data-player-settings]').focus({ preventScroll: true });
    arm();
  }
  function updateProgress() {
    if (!active || !video) return;
    const seek = controls.querySelector('[data-player-seek]');
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    seek.max = duration || 1;
    seek.disabled = !duration;
    seek.value = video.currentTime || 0;
    controls.querySelector('[data-player-time]').textContent =
      `${clockLabel(video.currentTime)} / ${clockLabel(duration)}`;
    const play = controls.querySelector('[data-remote-play]');
    play.textContent = video.paused ? '播放' : '暂停';
    play.setAttribute('aria-label', video.paused ? '播放视频' : '暂停视频');
  }
  function deactivate() {
    clearTimeout(timer);
    for (const [node, anchor] of moves.splice(0)) {
      anchor.before(node);
      anchor.remove();
    }
    controls?.remove();
    panel?.remove();
    controls = panel = null;
    active = false;
    stage.classList.remove('cinema', 'cinema-idle', 'cinema-fill', 'cinema-panel-open');
    dialog.classList.remove('cinema-dialog');
    stage.removeAttribute('tabindex');
    stage.style.removeProperty('--viewport-height');
    dialog.style.removeProperty('--viewport-height');
    if (video) video.controls = originalControls;
    enableRemote(remoteBefore);
  }
  function activate() {
    if (active) return;
    active = true;
    enableRemote(true);
    dialog.classList.add('cinema-dialog');
    stage.classList.add('cinema');
    stage.tabIndex = -1;
    if (video) video.controls = false;
    controls = document.createElement('div');
    controls.className = 'cinema-controls';
    controls.setAttribute('aria-label', '放映控制');
    controls.innerHTML = `${video ? '<div class="cinema-progress"><input type="range" data-player-seek min="0" max="1" step="1" value="0" aria-label="播放进度"><span data-player-time></span></div>' : ''}<div class="cinema-buttons"></div>`;
    const buttons = controls.querySelector('.cinema-buttons');
    for (const name of ['remote-play', 'remote-back', 'remote-forward', 'previous', 'next'])
      move(stage.querySelector(`[data-${name}]`), buttons);
    const count = stage.querySelector('.viewer-footer > span');
    if (count) {
      count.classList.add('cinema-count');
      move(count, buttons);
    }
    const settings = document.createElement('button');
    settings.dataset.playerSettings = '';
    settings.textContent = '播放设置';
    buttons.append(settings);
    panel = document.createElement('section');
    panel.className = 'cinema-panel';
    panel.hidden = true;
    panel.setAttribute('aria-label', '播放设置');
    panel.innerHTML =
      '<header><h3>播放设置</h3><button data-player-settings-close aria-label="关闭播放设置">返回画面</button></header><label>画面比例<select data-player-fit aria-label="画面显示方式"><option value="contain">完整显示</option><option value="cover">铺满屏幕（裁剪）</option></select></label>';
    for (const selector of [
      '.viewer-options',
      '[data-playback-status]',
      '.playback-details',
      '.viewer-details',
    ])
      move(stage.querySelector(selector), panel);
    stage.append(controls, panel);
    const fit = panel.querySelector('[data-player-fit]');
    fit.value = saved.fit === 'cover' ? 'cover' : 'contain';
    stage.classList.toggle('cinema-fill', fit.value === 'cover');
    settings.onclick = () => {
      show();
      panel.hidden = false;
      stage.classList.add('cinema-panel-open');
      clearTimeout(timer);
      panel.querySelector('[data-player-settings-close]').focus({ preventScroll: true });
    };
    panel.querySelector('[data-player-settings-close]').onclick = closePanel;
    fit.onchange = (event) => stage.classList.toggle('cinema-fill', event.target.value === 'cover');
    if (video)
      controls.querySelector('[data-player-seek]').oninput = (event) => {
        video.currentTime = Number(event.target.value);
        show();
      };
    updateProgress();
    show();
  }
  function sync() {
    if (disposed) return;
    const full = fullscreen() === stage;
    if (seenFullscreen && !full) pageFullscreen = false;
    seenFullscreen = full;
    if (document.body.classList.contains('tv-mode') || full || pageFullscreen) {
      activate();
      const height = Math.max(1, window.innerHeight) + 'px';
      // Read the actual WebView viewport; older kernels can report vh as zero.
      stage.style.setProperty('--viewport-height', height);
      dialog.style.setProperty('--viewport-height', height);
    } else if (active) deactivate();
  }
  async function toggleFullscreen() {
    if (fullscreen()) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else document.webkitExitFullscreen();
      return;
    }
    if (pageFullscreen) {
      pageFullscreen = false;
      sync();
      return;
    }
    pageFullscreen = true;
    sync();
    try {
      if (stage.requestFullscreen) await stage.requestFullscreen();
      else if (stage.webkitRequestFullscreen) stage.webkitRequestFullscreen();
      else if (video?.webkitEnterFullscreen) video.webkitEnterFullscreen();
      else toast('已铺满网页；当前浏览器未提供系统全屏');
    } catch {
      toast('系统全屏未获允许，已使用网页全屏');
    }
    show(true);
  }
  function handleKey(key) {
    if (!active || !dialog.open) return null;
    if (key === 'Back' || key === 'Escape') {
      if (!panel.hidden) {
        closePanel();
        return 'handled';
      }
      if (!fullscreen() && pageFullscreen) {
        pageFullscreen = false;
        sync();
        return 'handled';
      }
      return null;
    }
    if (key === 'Focus') {
      if (panel.hidden) show(true);
      else panel.querySelector('[data-player-settings-close]').focus();
      return 'handled';
    }
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Enter', ' '].includes(key)) {
      if (stage.classList.contains('cinema-idle')) {
        show(true);
        return 'handled';
      }
      show();
      if (
        video &&
        document.activeElement?.matches('[data-player-seek]') &&
        ['ArrowLeft', 'ArrowRight'].includes(key)
      ) {
        video.currentTime = Math.max(
          0,
          Math.min(video.duration || 0, video.currentTime + (key === 'ArrowLeft' ? -10 : 10)),
        );
        updateProgress();
        return 'handled';
      }
    }
    if (key.startsWith('Media')) show();
    return null;
  }
  function activity(event) {
    if (event?.type === 'focusin' && event.target === stage) return;
    show();
  }
  function playing() {
    updateProgress();
    arm();
  }
  function paused() {
    updateProgress();
    show();
  }
  function endVideoFullscreen() {
    pageFullscreen = false;
    sync();
  }
  const observer = new MutationObserver(sync);
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  for (const name of ['fullscreenchange', 'webkitfullscreenchange'])
    document.addEventListener(name, sync);
  window.addEventListener('resize', sync);
  for (const name of ['pointermove', 'pointerdown', 'focusin'])
    stage.addEventListener(name, activity);
  if (video) {
    video.addEventListener('webkitendfullscreen', endVideoFullscreen);
    for (const name of ['timeupdate', 'loadedmetadata'])
      video.addEventListener(name, updateProgress);
    for (const name of ['playing', 'seeked']) video.addEventListener(name, playing);
    for (const name of ['pause', 'waiting', 'error']) video.addEventListener(name, paused);
  }
  setPlayerRemote(handleKey);
  sync();
  return {
    toggleFullscreen,
    snapshot: () => ({
      pageFullscreen,
      fit: stage.classList.contains('cinema-fill') ? 'cover' : 'contain',
    }),
    focus: () => {
      sync();
      if (active) show(true);
    },
    dispose: () => {
      disposed = true;
      observer.disconnect();
      setPlayerRemote(null);
      for (const name of ['fullscreenchange', 'webkitfullscreenchange'])
        document.removeEventListener(name, sync);
      window.removeEventListener('resize', sync);
      for (const name of ['pointermove', 'pointerdown', 'focusin'])
        stage.removeEventListener(name, activity);
      if (video) {
        video.removeEventListener('webkitendfullscreen', endVideoFullscreen);
        for (const name of ['timeupdate', 'loadedmetadata'])
          video.removeEventListener(name, updateProgress);
        for (const name of ['playing', 'seeked']) video.removeEventListener(name, playing);
        for (const name of ['pause', 'waiting', 'error']) video.removeEventListener(name, paused);
      }
      if (active) deactivate();
    },
  };
}
