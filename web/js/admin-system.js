/* Author: donglixiao · Registration settings and paginated audit history. */
import { accountRequest } from './session.js';
import { escapeHTML as e } from './utils.js';
import { displayTime } from './admin-users.js';
export async function renderSettings(root, notify) {
  const settings = await accountRequest('/api/admin/settings');
  root.innerHTML = `<section class="admin-panel"><h2>家庭空间设置</h2><form style="max-width:480px"><label class="check-label"><input name="registration" type="checkbox" ${settings.registration ? 'checked' : ''} />允许家人自行注册普通账号</label><label>新视频的默认可见范围<select name="defaultVideoVisibility"><option value="all">全部用户可见</option><option value="admin">仅超级管理员可见</option></select></label><label>新照片的默认可见范围<select name="defaultVisibility"><option value="admin">仅超级管理员可见</option><option value="all">全部用户可见</option></select><small>已有素材保持各自的可见范围，不会随默认值改变。</small></label><label>记住登录的天数<input name="sessionDays" type="number" min="1" max="90" required value="${settings.sessionDays}" /><small>1–90 天，对之后的新登录生效。停用账号或重置密码会立即撤销已有登录。</small></label><button class="access-primary">保存设置</button></form><p class="access-note">角色权限固定为超级管理员和普通用户。普通用户只能浏览，不能编辑回忆或更改设置。</p></section>`;
  const form = root.querySelector('form');
  form.elements.defaultVisibility.value = settings.defaultVisibility;
  form.elements.defaultVideoVisibility.value =
    settings.defaultVideoVisibility ?? settings.defaultVisibility;
  form.onsubmit = async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      await accountRequest('/api/admin/settings', 'PATCH', {
        registration: form.elements.registration.checked,
        defaultVisibility: form.elements.defaultVisibility.value,
        defaultVideoVisibility: form.elements.defaultVideoVisibility.value,
        sessionDays: Number(form.elements.sessionDays.value),
      });
      notify('设置已保存。');
    } catch (error) {
      notify(error.message);
    } finally {
      button.disabled = false;
    }
  };
}
const actions = {
  login: '登录',
  logout: '退出登录',
  'account.setup': '创建超级管理员',
  'account.create': '创建账号',
  'account.enabled': '调整账号状态',
  'account.enable': '启用账号',
  'account.disable': '停用账号',
  'account.password': '修改或重置密码',
  'account.recover': '本机恢复管理员密码',
  'account.role': '分配普通用户角色',
  'media.view': '查看原片',
  'media.visibility': '修改可见范围',
  'settings.update': '修改基础设置',
  'media.edit': '编辑回忆',
  'media.batch': '批量编辑回忆',
  'library.scan': '刷新素材目录',
  'library.import': '导入编辑记录',
};
export async function renderLogs(root, notify) {
  let result = await accountRequest('/api/admin/logs');
  root.innerHTML = `<section class="admin-panel"><h2>访问与操作日志</h2><p class="access-note">按 UTC 日期归档，时间按此设备的时区显示。同一用户、设备 IP 和原片在一分钟内的播放分段请求合并为一次访问。</p><div class="admin-toolbar"><select id="log-day" aria-label="日志日期">${result.days.map((day) => `<option>${e(day)}</option>`).join('')}</select></div><div id="log-list"></div><button id="logs-more" class="admin-more">更早的记录</button></section>`;
  const list = root.querySelector('#log-list');
  const more = root.querySelector('#logs-more');
  function append() {
    list.insertAdjacentHTML(
      'beforeend',
      result.items
        .map(
          (log) =>
            `<article class="admin-log"><time>${e(displayTime(log.time))}</time><strong>${e(log.actor || '未登录访客')} · ${e(actions[log.action] || log.action)}</strong><span>${e(log.outcome === 'ok' ? '成功' : '未通过')} · ${e(log.ip || '本机')}<br /><span class="admin-meta">${e(log.target)}</span></span></article>`,
        )
        .join(''),
    );
    more.hidden = result.cursor === null;
    if (!list.children.length) list.textContent = '这一天还没有日志。';
  }
  async function load(older) {
    more.disabled = true;
    try {
      const day = root.querySelector('#log-day').value;
      result = await accountRequest(
        `/api/admin/logs?day=${encodeURIComponent(day)}${older ? '&cursor=' + result.cursor : ''}`,
      );
      if (!older) list.replaceChildren();
      append();
    } catch (error) {
      notify(error.message);
    } finally {
      more.disabled = false;
    }
  }
  root.querySelector('#log-day').onchange = () => load(false);
  more.onclick = () => load(true);
  append();
}
