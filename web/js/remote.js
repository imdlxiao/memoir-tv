/* Author: donglixiao · Shared D-pad navigation and WebView remote cooperation. */
const tvAgent = /TVBrowser|Android TV|SmartTV|SMART-TV|GoogleTV|HbbTV/i.test(navigator.userAgent);
let enabled = tvAgent;
let lastFocus = null;
let entered = false;
const selectors = 'button,a[href],input,textarea,select,summary,[tabindex],[role="button"]';
export function enableRemote(value = true) {
  enabled = value || tvAgent;
  document.documentElement.classList.toggle('tv-remote', enabled);
}
function scope() {
  const dialogs = [...document.querySelectorAll('dialog[open]')];
  return dialogs[dialogs.length - 1] || document;
}
function targets(root = scope()) {
  return [...root.querySelectorAll(selectors)].filter((node) => {
    const rect = node.getBoundingClientRect();
    return (
      !node.disabled &&
      node.tabIndex >= 0 &&
      rect.width > 0 &&
      rect.height > 0 &&
      getComputedStyle(node).visibility !== 'hidden' &&
      !node.closest('[hidden],dialog:not([open])')
    );
  });
}
function focus(node) {
  if (!node) return;
  node.focus({ preventScroll: true });
  node.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  lastFocus = node;
}
export function handleRemoteKey(key) {
  if (!enabled) enableRemote();
  const root = scope();
  const current = document.activeElement;
  const choices = targets(root);
  if (key === 'Back' || key === 'Escape') {
    if (document.fullscreenElement) {
      document.exitFullscreen();
      return 'handled';
    }
    if (document.webkitFullscreenElement) {
      document.webkitExitFullscreen();
      return 'handled';
    }
    if (root !== document) {
      root.close();
      return 'handled';
    }
    if (document.body.classList.contains('tv-mode')) {
      document.dispatchEvent(new CustomEvent('memoir:tv-exit'));
      return 'handled';
    }
    return 'unhandled';
  }
  if (key.startsWith('Media')) {
    const video = root.querySelector('video');
    if (video) {
      if (key === 'MediaFastForward' && Number.isFinite(video.duration))
        video.currentTime = Math.min(video.duration, video.currentTime + 10);
      else if (key === 'MediaRewind') video.currentTime = Math.max(0, video.currentTime - 10);
      else if (key === 'MediaPause' || (key === 'MediaPlayPause' && !video.paused)) video.pause();
      else if (key === 'MediaPlay' || key === 'MediaPlayPause') video.play().catch(() => {});
      return 'handled';
    }
    return 'unhandled';
  }
  if (key === 'Focus' || !choices.includes(current)) {
    focus(
      entered && choices.includes(lastFocus)
        ? lastFocus
        : choices.find((node) => node.matches('input,[data-action="open"]')) || choices[0],
    );
    entered = true;
    return 'handled';
  }
  const horizontal = key === 'ArrowLeft' || key === 'ArrowRight';
  const negative = key === 'ArrowLeft' || key === 'ArrowUp';
  if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(key)) return 'native';
  if (current.matches('input,textarea') && horizontal) return 'native';
  if (current.matches('select') && horizontal) {
    const options = [...current.options].filter((option) => !option.disabled);
    const index = options.findIndex((option) => option.selected);
    const next = options[Math.max(0, Math.min(options.length - 1, index + (negative ? -1 : 1)))];
    if (next) {
      current.value = next.value;
      current.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return 'handled';
  }
  const rect = current.getBoundingClientRect();
  let best = null,
    score = Infinity;
  for (const node of choices) {
    if (node === current) continue;
    const candidate = node.getBoundingClientRect();
    const dx = candidate.left + candidate.width / 2 - rect.left - rect.width / 2;
    const dy = candidate.top + candidate.height / 2 - rect.top - rect.height / 2;
    const along = (horizontal ? dx : dy) * (negative ? -1 : 1);
    const cross = Math.abs(horizontal ? dy : dx);
    if (along <= 4) continue;
    const rank = along + cross * 3;
    if (rank < score) {
      score = rank;
      best = node;
    }
  }
  if (best) focus(best);
  else if (key === 'ArrowUp' && root === document && window.scrollY <= 0) return 'toolbar';
  else if (!horizontal) {
    const container = root === document ? window : root;
    container.scrollBy(0, (negative ? -1 : 1) * window.innerHeight * 0.5);
  }
  return 'handled';
}
enableRemote(enabled);
window.MemoirTV = { handleKey: handleRemoteKey };
document.addEventListener(
  'keydown',
  (event) => {
    if (!enabled || event.altKey || event.ctrlKey || event.metaKey) return;
    if (
      ![
        'ArrowUp',
        'ArrowDown',
        'ArrowLeft',
        'ArrowRight',
        'Escape',
        'GoBack',
        'BrowserBack',
        'MediaPlayPause',
        'MediaPlay',
        'MediaPause',
        'MediaFastForward',
        'MediaRewind',
      ].includes(event.key)
    )
      return;
    const result = handleRemoteKey(
      ['GoBack', 'BrowserBack'].includes(event.key) ? 'Back' : event.key,
    );
    if (result === 'handled' || result === 'toolbar') {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },
  true,
);
document.addEventListener('focusin', (event) => {
  if (event.target.matches(selectors)) lastFocus = event.target;
});
export const isRemote = () => enabled;
