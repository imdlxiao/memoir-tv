/* Author: donglixiao · Visible-page library sync without interrupting edits or playback. */
export function startLibrarySync(refresh) {
  let busy = false;
  const tick = async () => {
    if (busy || document.hidden || document.querySelector('dialog[open]')) return;
    busy = true;
    try {
      await refresh();
    } catch {
      // Retain the current view during a temporary disconnect; the next tick retries.
    } finally {
      busy = false;
    }
  };
  setInterval(tick, 5000);
  document.addEventListener('visibilitychange', tick);
  window.addEventListener('focus', tick);
}
