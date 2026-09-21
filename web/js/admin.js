/* Author: donglixiao · Admin navigation and shared presentation helpers. */
import { accountRequest, watchSession } from './session.js';
import './access-navigation.js';
import { renderUsers } from './admin-users.js';
import { renderVisibility } from './admin-visibility.js';
import { renderSettings, renderLogs } from './admin-system.js';
const content = document.querySelector('#admin-content');
const message = document.querySelector('#admin-message');
let generation = 0;
async function open(panel) {
  const current = ++generation;
  message.textContent = '正在读取…';
  document
    .querySelectorAll('[data-panel]')
    .forEach((button) => button.setAttribute('aria-pressed', button.dataset.panel === panel));
  const surface = document.createElement('div');
  try {
    await {
      users: renderUsers,
      visibility: renderVisibility,
      settings: renderSettings,
      logs: renderLogs,
    }[panel](surface, (text) => {
      message.textContent = text;
    });
    if (generation !== current) return;
    content.replaceChildren(surface);
    message.textContent = '';
  } catch (error) {
    if (generation === current) message.textContent = error.message;
  }
}
document.querySelector('.admin-tabs').onclick = (event) => {
  const button = event.target.closest('[data-panel]');
  if (button) open(button.dataset.panel);
};
async function initialize() {
  try {
    const { user } = await accountRequest('/api/auth/me');
    if (!user) location.replace('/login.html');
    else if (user.role !== 'admin') location.replace('/?denied=1');
    else {
      document.querySelector('#admin-identity').textContent = `${user.username} · 超级管理员`;
      watchSession();
      open(
        new URLSearchParams(location.search).get('panel') === 'visibility' ? 'visibility' : 'users',
      );
    }
  } catch (error) {
    message.textContent = error.message;
  }
}
initialize();
window.memoirReady = true;
