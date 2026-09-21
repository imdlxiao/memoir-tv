/* Author: donglixiao · Family account creation and lifecycle management. */
import { accountRequest } from './session.js';
import { escapeHTML as e } from './utils.js';
export const displayTime = (value) =>
  value
    ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString('zh-CN')
    : '尚未登录';
export async function renderUsers(root, notify) {
  const { users } = await accountRequest('/api/admin/users');
  root.innerHTML = `<div class="admin-grid"><section class="admin-panel"><h2>邀请一位家人</h2><p class="access-note">新建账号为普通用户，只能浏览向其开放的内容。</p><form id="create-user"><label>用户名<input name="username" required minlength="3" maxlength="32" autocomplete="off" /></label><label>初始密码<input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password" /><small>至少 12 位，包含字母和数字。</small></label><label>手机号（可选）<input name="phone" type="tel" maxlength="24" /></label><label>角色<select name="role"><option value="user">普通用户</option></select></label><button class="access-primary">创建账号</button></form></section><section class="admin-panel"><h2>家人账号 · ${users.length}</h2><div id="user-list">${users.map((user) => `<article class="admin-row" data-user="${e(user.id)}"><h3>${e(user.username)} <span class="admin-meta">${user.role === 'admin' ? '超级管理员' : '普通用户'} · ${user.enabled ? '已启用' : '已停用'}</span></h3><div class="admin-meta">创建：${e(displayTime(user.createdAt))}<br />最后登录：${e(displayTime(user.lastLogin))}${user.phone ? '<br />手机号：' + e(user.phone) : ''}</div>${user.role !== 'admin' ? `<div class="admin-actions"><button data-toggle>${user.enabled ? '停用账号' : '启用账号'}</button></div><form data-reset><label>重置密码<input name="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password" placeholder="新密码，至少 12 位" /></label><div class="admin-actions"><button>重置并退出全部设备</button></div></form>` : '<span class="access-note">最高权限账号受到保护，修改密码请返回首页的账号菜单。</span>'}</article>`).join('')}</div></section></div>`;
  const create = root.querySelector('#create-user');
  create.onsubmit = async (event) => {
    event.preventDefault();
    const button = create.querySelector('button');
    button.disabled = true;
    try {
      await accountRequest('/api/admin/users', 'POST', Object.fromEntries(new FormData(create)));
      await renderUsers(root, notify);
      notify('账号已创建。');
    } catch (error) {
      notify(error.message);
      button.disabled = false;
    }
  };
  root.querySelectorAll('[data-user]').forEach((row) => {
    const user = users.find((user) => user.id === row.dataset.user);
    const toggle = row.querySelector('[data-toggle]');
    if (toggle)
      toggle.onclick = async () => {
        toggle.disabled = true;
        try {
          await accountRequest(`/api/admin/users/${user.id}`, 'PATCH', { enabled: !user.enabled });
          await renderUsers(root, notify);
          notify(user.enabled ? '账号已停用，已有登录立即失效。' : '账号已启用，请重新登录。');
        } catch (error) {
          notify(error.message);
          toggle.disabled = false;
        }
      };
    const reset = row.querySelector('[data-reset]');
    if (reset)
      reset.onsubmit = async (event) => {
        event.preventDefault();
        const button = reset.querySelector('button');
        button.disabled = true;
        try {
          await accountRequest(`/api/admin/users/${user.id}`, 'PATCH', {
            password: reset.elements.password.value,
          });
          reset.reset();
          notify('密码已重置，该用户的所有登录凭证已失效。');
        } catch (error) {
          notify(error.message);
        } finally {
          button.disabled = false;
        }
      };
  });
}
