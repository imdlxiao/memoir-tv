/* Author: donglixiao · Spatial keyboard navigation for living-room displays. */
import { $ } from './utils.js';
import { enableRemote } from './remote.js';
export function setTV(enabled) {
  enableRemote(enabled);
  document.body.classList.toggle('tv-mode', enabled);
  let exit = $('#tv-exit');
  if (enabled && !exit) {
    exit = document.createElement('button');
    exit.id = 'tv-exit';
    exit.className = 'tv-exit';
    exit.textContent = '退出放映室';
    exit.onclick = () => setTV(false);
    $('.topbar-actions').prepend(exit);
  }
  if (exit) exit.hidden = !enabled;
  if (enabled) {
    window.scrollTo({ top: 0 });
    const previous = document.activeElement;
    setTimeout(() => {
      if (document.activeElement === previous) $('.media-frame')?.focus();
    }, 100);
  }
}
export function initializeTV() {
  document.addEventListener('memoir:tv-exit', () => setTV(false));
  if (/TVBrowser|Android TV|SmartTV|SMART-TV|GoogleTV|HbbTV/i.test(navigator.userAgent))
    setTV(true);
}
