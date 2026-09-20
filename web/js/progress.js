/* Author: donglixiao · Private, per-browser playback progress with bounded storage. */
const KEY = `memoir-progress-v1:${location.pathname}`;
function readAll() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}
function fingerprint(item) {
  return `${item.size || 0}:${item.modified || 0}`;
}
export function readProgress(item) {
  const value = readAll()[item.id];
  return value &&
    value.fingerprint === fingerprint(item) &&
    Number.isFinite(value.time) &&
    value.time >= 5 &&
    Number.isFinite(value.duration) &&
    value.time < value.duration - 5
    ? value
    : null;
}
export function writeProgress(item, time, duration) {
  if (!Number.isFinite(time) || !Number.isFinite(duration) || duration <= 0) return;
  try {
    const all = readAll();
    if (time < 5 || duration - time <= 5) delete all[item.id];
    else all[item.id] = { time, duration, fingerprint: fingerprint(item), updatedAt: Date.now() };
    const entries = Object.entries(all)
      .sort((a, b) => b[1].updatedAt - a[1].updatedAt)
      .slice(0, 500);
    localStorage.setItem(KEY, JSON.stringify(Object.fromEntries(entries)));
  } catch {
    /* Storage disabled or full must never prevent playback. */
  }
}
export function clockLabel(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(value / 3600),
    minutes = Math.floor((value % 3600) / 60),
    rest = String(value % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}
export function attachProgress(video, item, onResume) {
  let lastSave = 0,
    restoring = true;
  const persist = () => {
    if (!restoring && video.readyState >= 1) writeProgress(item, video.currentTime, video.duration);
  };
  const loaded = () => {
    const previous = readProgress(item);
    if (previous && previous.time < video.duration - 5) {
      video.currentTime = previous.time;
      onResume(previous.time);
    }
    restoring = false;
  };
  const time = () => {
    if (Date.now() - lastSave > 5000) {
      persist();
      lastSave = Date.now();
    }
  };
  const ended = () => writeProgress(item, video.duration, video.duration);
  video.addEventListener('loadedmetadata', loaded);
  video.addEventListener('timeupdate', time);
  video.addEventListener('pause', persist);
  video.addEventListener('seeked', persist);
  video.addEventListener('ended', ended);
  window.addEventListener('pagehide', persist);
  return () => {
    persist();
    video.removeEventListener('loadedmetadata', loaded);
    video.removeEventListener('timeupdate', time);
    video.removeEventListener('pause', persist);
    video.removeEventListener('seeked', persist);
    video.removeEventListener('ended', ended);
    window.removeEventListener('pagehide', persist);
  };
}
