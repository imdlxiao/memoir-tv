/* Author: donglixiao · Playback quality, reusable copies and local buffer diagnostics. */
import { getMode } from './api.js';
import { mediaURL } from './utils.js';
import { attachDiagnostics } from './playback-diagnostics.js';

export function attachPlayback(video, item, root) {
  const select = root.querySelector('[data-quality]');
  const status = root.querySelector('[data-playback-status]');
  const prepare = root.querySelector('[data-prepare-playback]');
  let disposed = false,
    poll = null,
    busy = false,
    rendition = null,
    createPending = false;
  let pendingRestore = null;
  const library = getMode() === 'library';
  const endpoint = `/api/playback/${encodeURIComponent(item.id)}`;
  if (!library) {
    select.value = 'original';
    select.disabled = true;
    prepare.hidden = true;
    status.textContent = '静态副本播放原片';
  }
  const restore = () => {
    if (!pendingRestore) return;
    const saved = pendingRestore;
    pendingRestore = null;
    if (saved.time !== null && Number.isFinite(video.duration))
      video.currentTime = Math.min(saved.time, Math.max(0, video.duration - 0.1));
    video.playbackRate = saved.rate;
    if (!saved.paused) video.play().catch(() => {});
  };
  video.addEventListener('loadedmetadata', restore);
  const switchSource = (url) => {
    const next = new URL(url, location.href).href;
    if (video.src === next) return;
    pendingRestore = pendingRestore || {
      time: video.readyState ? video.currentTime || 0 : null,
      paused: video.paused,
      rate: video.playbackRate,
    };
    video.src = next;
    video.load();
  };
  const waitForSmooth = () => {
    if (!video.getAttribute('src')) return;
    pendingRestore = pendingRestore || {
      time: video.readyState ? video.currentTime : null,
      paused: video.paused,
      rate: video.playbackRate,
    };
    video.pause();
    video.removeAttribute('src');
    video.load();
  };
  const apply = () => {
    prepare.hidden =
      !library ||
      select.value === 'original' ||
      ['ready', 'processing', 'queued', 'failed'].includes(rendition?.state);
    if (select.value === 'original') {
      switchSource(mediaURL(item));
      status.textContent = '原画 · 原始文件';
    } else if (rendition?.state === 'ready') {
      switchSource(rendition.url);
      status.textContent = '流畅版 · 最高 720p · H.264';
    } else {
      if (select.value === 'smooth') waitForSmooth();
      else if (!video.getAttribute('src')) switchSource(mediaURL(item));
      const active =
        select.value === 'smooth' ? '已停止原画，等待流畅版；也可切回原画' : '实际仍在播放原画';
      status.textContent =
        rendition?.state === 'processing'
          ? `流畅版生成中 ${rendition.progress || 0}% · ${active}`
          : `${rendition?.message || '流畅版尚未生成'} · ${active}`;
    }
  };
  const read = async (create = false) => {
    if (disposed || !library) return;
    if (busy) {
      createPending = createPending || create;
      return;
    }
    busy = true;
    try {
      const response = await fetch(endpoint, {
        method: create ? 'POST' : 'GET',
        cache: 'no-store',
        headers: create ? { 'Content-Type': 'application/json' } : {},
        body: create ? '{}' : undefined,
      });
      const result = await response.json();
      if (disposed) return;
      if (!response.ok) {
        if ([401, 403, 404].includes(response.status)) {
          video.pause();
          video.removeAttribute('src');
          video.load();
        }
        throw new Error(result.error || `播放信息读取失败 (${response.status})`);
      }
      rendition = result;
      apply();
      clearTimeout(poll);
      if (['processing', 'queued', 'busy'].includes(result.state))
        poll = setTimeout(() => read(), 2500);
    } catch (error) {
      if (!disposed) status.textContent = error.message;
    } finally {
      busy = false;
      if (createPending && !disposed) {
        createPending = false;
        read(true);
      }
    }
  };
  select.onchange = () => {
    apply();
    if (select.value === 'smooth' && rendition?.state !== 'ready') read(true);
  };
  prepare.onclick = () => read(true);
  const detachDiagnostics = attachDiagnostics(video, item, root, () => rendition);
  if (library) read();
  return () => {
    disposed = true;
    detachDiagnostics();
    clearTimeout(poll);
    video.removeEventListener('loadedmetadata', restore);
  };
}
