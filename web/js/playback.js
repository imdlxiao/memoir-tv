/* Author: donglixiao · Playback quality, reusable copies and local buffer diagnostics. */
import { getMode } from './api.js';
import { mediaURL } from './utils.js';

export function attachPlayback(video, item, root) {
  const select = root.querySelector('[data-quality]');
  const status = root.querySelector('[data-playback-status]');
  const prepare = root.querySelector('[data-prepare-playback]');
  const metrics = root.querySelector('[data-playback-metrics]');
  let disposed = false,
    poll = null,
    busy = false,
    rendition = null,
    stalls = 0,
    waiting = false;
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
    pendingRestore = {
      time: video.readyState ? video.currentTime || 0 : null,
      paused: video.paused,
      rate: video.playbackRate,
    };
    video.src = next;
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
      status.textContent =
        rendition?.state === 'processing'
          ? `流畅版生成中 ${rendition.progress || 0}% · 目前播放原画`
          : rendition?.message || '目前播放原画，可生成流畅版降低缓冲等待';
    }
  };
  const read = async (create = false) => {
    if (busy || disposed || !library) return;
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
    }
  };
  select.onchange = () => {
    apply();
    if (select.value === 'smooth' && rendition?.state !== 'ready') read(true);
  };
  prepare.onclick = () => read(true);
  const onWaiting = () => {
    if (!video.seeking && !video.paused && video.currentTime > 0 && !waiting) stalls++;
    waiting = true;
  };
  const onPlaying = () => {
    waiting = false;
  };
  video.addEventListener('waiting', onWaiting);
  video.addEventListener('playing', onPlaying);
  const diagnose = () => {
    let ahead = 0;
    for (let i = 0; i < video.buffered.length; i++) {
      if (
        video.buffered.start(i) <= video.currentTime &&
        video.buffered.end(i) >= video.currentTime
      )
        ahead = video.buffered.end(i) - video.currentTime;
    }
    const quality = video.getVideoPlaybackQuality?.();
    const dropped = quality?.droppedVideoFrames ?? video.webkitDroppedFrameCount;
    const duration = item.capture?.duration || video.duration;
    const bitrate = duration > 0 ? ((item.size * 8) / duration / 1000000).toFixed(1) : '未知';
    metrics.textContent =
      `已缓冲 ${ahead.toFixed(1)} 秒 · 等待 ${stalls} 次 · 丢帧 ${dropped ?? '浏览器未提供'} · 原片平均 ${bitrate} Mbps。` +
      (waiting && ahead < 1
        ? ' 缓冲不足：后续数据暂未到达，可切换流畅版。'
        : ' 缓冲充足仍跳帧时，请尝试流畅版降低解码负担。');
  };
  const timer = setInterval(diagnose, 1000);
  diagnose();
  if (library) read();
  return () => {
    disposed = true;
    clearInterval(timer);
    clearTimeout(poll);
    video.removeEventListener('loadedmetadata', restore);
    video.removeEventListener('waiting', onWaiting);
    video.removeEventListener('playing', onPlaying);
  };
}
