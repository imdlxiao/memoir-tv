/* Author: donglixiao · Account menu, password changes and role-aware navigation. */
import { accountRequest, watchSession } from './session.js';
import { state } from './store.js';
import { $, escapeHTML as e, setupDialog, openDialog, toast } from './utils.js';

export function canEdit() {
  return state.mode === 'static' || state.user?.role === 'admin';
}
export function initializeAccount(user) {
  if (!user) return;
  state.user = user;
  document.documentElement.dataset.role = user.role;
  const button = $('#account-button');
  button.hidden = false;
  button.textContent = user.username;
  button.setAttribute('aria-label', `我的账号：${user.username}`);
  const dialog = document.createElement('dialog');
  dialog.className = 'account-dialog';
  dialog.id = 'account-dialog';
  dialog.setAttribute('aria-label', '我的账号');
  dialog.innerHTML = `<button class="quiet-button" data-close>关闭</button><h2>${e(user.username)}</h2><p>${user.role === 'admin' ? '超级管理员 · 家庭空间的守护者' : '普通用户 · 浏览向你开放的回忆'}</p><nav>${user.role === 'admin' ? '<a href="/admin.html">用户、可见权限与系统管理 →</a>' : ''}<button class="secondary-button" id="logout-button">退出登录</button></nav><details><summary>修改我的密码</summary><form><label>当前密码<input name="currentPassword" type="password" autocomplete="current-password" required /></label><label>新密码<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required /><small>至少 12 位，包含字母和数字。</small></label><p role="status"></p><button class="primary-button">保存并退出所有设备</button></form></details>`;
  document.body.append(dialog);
  setupDialog(dialog);
  $('[data-close]', dialog).onclick = () => dialog.close();
  button.onclick = () => openDialog(dialog);
  if (user.role !== 'admin') {
    $('#mobile-library').innerHTML = '<span>账号</span>';
    $('#mobile-library').onclick = () => openDialog(dialog);
  }
  $('#logout-button').onclick = async () => {
    try {
      await accountRequest('/api/auth/logout', 'POST', {});
      location.replace('/login.html');
    } catch (error) {
      toast(error.message);
    }
  };
  $('form', dialog).onsubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = $('button', form);
    submit.disabled = true;
    try {
      await accountRequest('/api/auth/password', 'POST', Object.fromEntries(new FormData(form)));
      location.replace('/login.html?expired=1');
    } catch (error) {
      $('[role=status]', form).textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  };
  watchSession(() => {
    if (user.role !== 'admin') location.reload();
  });
  if (new URLSearchParams(location.search).has('denied')) toast('该管理页面仅超级管理员可访问');
}
