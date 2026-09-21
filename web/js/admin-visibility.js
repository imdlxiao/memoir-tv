/* Author: donglixiao · Per-media audience editing with paginated presentation. */
import { accountRequest } from './session.js';
import { escapeHTML as e, titleOf, safeURL } from './utils.js';
export async function renderVisibility(root, notify) {
  const [catalog, { users }] = await Promise.all([
    accountRequest('/api/catalog'),
    accountRequest('/api/admin/users'),
  ]);
  const people = users.filter((user) => user.role === 'user');
  root.innerHTML =
    '<section class="admin-panel"><h2>每段回忆，分享给谁</h2><p class="access-note">照片和视频使用同一套可见权限。超级管理员始终可见；普通用户无法通过原片链接绕过限制。</p><div class="admin-toolbar"><input id="visibility-search" type="search" aria-label="搜索内容" placeholder="搜索标题或文件名" /><select id="visibility-filter" aria-label="筛选可见范围"><option value="">所有可见范围</option><option value="admin">仅超级管理员</option><option value="all">全部用户</option><option value="selected">指定用户</option></select></div><p id="visibility-count" class="admin-meta"></p><div id="visibility-list"></div><button id="visibility-more" class="admin-more">加载更多</button></section>';
  let limit = 20;
  function render() {
    const query = root.querySelector('#visibility-search').value.trim().toLocaleLowerCase();
    const scope = root.querySelector('#visibility-filter').value;
    const items = catalog.items.filter(
      (item) =>
        (!scope || item.visibility.scope === scope) &&
        `${titleOf(item)} ${item.filename}`.toLocaleLowerCase().includes(query),
    );
    root.querySelector('#visibility-count').textContent = `${items.length} 条回忆`;
    root.querySelector('#visibility-more').hidden = items.length <= limit;
    root.querySelector('#visibility-list').innerHTML = items
      .slice(0, limit)
      .map(
        (item) =>
          `<article class="admin-row visibility-row" data-media="${e(item.id)}">${item.thumbnail ? `<img src="${e(safeURL(item.thumbnail))}" alt="" loading="lazy" />` : '<div class="visibility-placeholder"></div>'}<form><h3>${e(titleOf(item))}</h3><span class="admin-meta">${item.kind === 'video' ? '视频' : '照片'} · ${e(item.filename)}</span><label>可见范围<select name="scope">${[
            ['all', '全部用户可见'],
            ['admin', '仅超级管理员可见'],
            ['selected', '指定用户可见'],
          ]
            .map(
              ([key, label]) =>
                `<option value="${key}" ${item.visibility.scope === key ? 'selected' : ''}>${label}</option>`,
            )
            .join(
              '',
            )}</select></label><fieldset class="visibility-people" ${item.visibility.scope !== 'selected' ? 'hidden' : ''}><legend>选择家人</legend>${people.length ? people.map((user) => `<label><input type="checkbox" name="users" value="${e(user.id)}" ${item.visibility.users.includes(user.id) ? 'checked' : ''} />${e(user.username)}${user.enabled ? '' : '（已停用）'}</label>`).join('') : '<small>请先在家人账号中创建普通用户。</small>'}</fieldset><div class="admin-actions"><button>保存可见范围</button><span class="admin-meta" role="status"></span></div></form></article>`,
      )
      .join('');
    root.querySelectorAll('[data-media]').forEach((row) => {
      const item = catalog.items.find((item) => item.id === row.dataset.media);
      const form = row.querySelector('form');
      form.elements.scope.onchange = () => {
        form.querySelector('fieldset').hidden = form.elements.scope.value !== 'selected';
      };
      form.onsubmit = async (event) => {
        event.preventDefault();
        const button = form.querySelector('button');
        button.disabled = true;
        const status = form.querySelector('[role=status]');
        try {
          const data = new FormData(form);
          item.visibility = await accountRequest(`/api/admin/visibility/${item.id}`, 'PATCH', {
            scope: data.get('scope'),
            users: data.getAll('users'),
          });
          status.textContent = '已保存，即时生效';
          notify('可见范围已保存。');
        } catch (error) {
          status.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      };
    });
  }
  root.querySelector('#visibility-search').oninput = () => {
    limit = 20;
    render();
  };
  root.querySelector('#visibility-filter').onchange = () => {
    limit = 20;
    render();
  };
  root.querySelector('#visibility-more').onclick = () => {
    limit += 20;
    render();
  };
  render();
}
