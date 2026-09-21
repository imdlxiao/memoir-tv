/* Author: donglixiao · Report the resource actually selected by the media engine. */
export function attachDiagnostics(video, item, root, getRendition) {
  const metrics = root.querySelector('[data-playback-metrics]');
  const test = root.querySelector('[data-playback-test]');
  const result = root.querySelector('[data-playback-test-result]');
  let stalls = 0,
    waiting = false,
    waitingSince = 0,
    waited = 0,
    previous = null;
  let disposed = false,
    controller = null;
  const actual = () => {
    if (!video.getAttribute('src') || !video.currentSrc) return { label: '尚未加载', size: 0 };
    const url = new URL(video.currentSrc, location.href);
    const smooth =
      url.origin === location.origin && url.pathname === `/playback/${encodeURIComponent(item.id)}`;
    return {
      label: smooth ? '流畅版 H.264' : '原画',
      size: smooth ? getRendition()?.size : item.size,
    };
  };
  const onWaiting = () => {
    if (video.seeking || video.paused || video.currentTime === 0 || waiting) return;
    stalls++;
    waiting = true;
    waitingSince = performance.now();
  };
  const onPlaying = () => {
    if (waiting) waited += performance.now() - waitingSince;
    waiting = false;
  };
  const reset = () => {
    onPlaying();
    stalls = 0;
    waited = 0;
    previous = null;
  };
  const diagnose = () => {
    let ahead = 0;
    for (let i = 0; i < video.buffered.length; i++) {
      if (
        video.buffered.start(i) <= video.currentTime + 0.05 &&
        video.buffered.end(i) >= video.currentTime
      )
        ahead = video.buffered.end(i) - video.currentTime;
    }
    const q = video.getVideoPlaybackQuality?.();
    const dropped = q?.droppedVideoFrames ?? video.webkitDroppedFrameCount;
    const total = q?.totalVideoFrames ?? video.webkitDecodedFrameCount;
    const recent =
      previous && total > previous.total && dropped >= previous.dropped
        ? `${((100 * (dropped - previous.dropped)) / (total - previous.total)).toFixed(1)}%`
        : '暂无样本';
    previous = { dropped, total };
    const source = actual();
    const duration = video.duration || item.capture?.duration;
    const bitrate =
      source.size && duration > 0
        ? `${((source.size * 8) / duration / 1000000).toFixed(2)} Mbps`
        : '待加载';
    const seconds = (waited + (waiting ? performance.now() - waitingSince : 0)) / 1000;
    const hint = !video.getAttribute('src')
      ? '等待流畅版就绪，或选择原画播放。'
      : waiting && ahead < 1
        ? '当前缓冲不足，请暂停并检测连接。'
        : ahead >= 3 && Number.parseFloat(recent) > 5
          ? '缓冲充足但仍丢帧，可能是设备解码或渲染负担。'
          : '下方可检测当前设备到素材电脑的传输。';
    metrics.textContent = `实际来源：${source.label} · 当前文件平均 ${bitrate} · ${video.videoWidth || '—'} × ${video.videoHeight || '—'} · ${video.playbackRate}×。已缓冲 ${ahead.toFixed(1)} 秒 · 等待 ${stalls} 次 / ${seconds.toFixed(1)} 秒 · 累计丢帧 ${dropped ?? '未提供'} · 最近一秒丢帧率 ${recent}。${hint}`;
    test.disabled = !video.getAttribute('src') || !video.currentSrc || !!controller;
  };
  test.onclick = async () => {
    const url = video.currentSrc;
    if (!url || controller) return;
    video.pause();
    controller = new AbortController();
    test.disabled = true;
    result.textContent = '已暂停播放，正在读取一小段当前视频…';
    const timeout = setTimeout(() => controller?.abort(), 15000);
    const started = performance.now();
    try {
      const response = await fetch(url, {
        headers: { Range: 'bytes=0-524287' },
        cache: 'no-store',
        signal: controller.signal,
      });
      if (response.status !== 206) {
        controller.abort();
        throw new Error(`分段读取失败，HTTP ${response.status}`);
      }
      const data = await response.arrayBuffer();
      const elapsed = (performance.now() - started) / 1000;
      if (!disposed)
        result.textContent = `本次读取 ${(data.byteLength / 1024).toFixed(0)} KB，用时 ${elapsed.toFixed(2)} 秒，约 ${((data.byteLength * 8) / elapsed / 1000000).toFixed(2)} Mbps（包含请求延迟，仅代表本次取样）。点击播放继续。`;
    } catch (error) {
      if (!disposed)
        result.textContent =
          error.name === 'AbortError' ? '读取超过 15 秒，请检查当前连接路径。' : error.message;
    } finally {
      clearTimeout(timeout);
      controller = null;
      if (!disposed) diagnose();
    }
  };
  for (const event of ['playing', 'pause', 'seeking']) video.addEventListener(event, onPlaying);
  video.addEventListener('waiting', onWaiting);
  video.addEventListener('loadstart', reset);
  const timer = setInterval(diagnose, 1000);
  diagnose();
  return () => {
    disposed = true;
    clearInterval(timer);
    controller?.abort();
    for (const event of ['playing', 'pause', 'seeking'])
      video.removeEventListener(event, onPlaying);
    video.removeEventListener('waiting', onWaiting);
    video.removeEventListener('loadstart', reset);
  };
}
