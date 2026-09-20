/* Author: donglixiao · Scan controls, portable backups, and library status. */
import { icon } from './icons.js';
import { $, openDialog, toast, downloadJSON, fileSize } from './utils.js';
import { backup, importBackup, startScan, scanStatus, getMode } from './api.js';
export function openLibrary(items, refresh, enterTV) {
  const dialog = $('#library-dialog'),
    local = getMode() === 'library';
  function updateSummary(catalog) {
    const current = catalog.items;
    $('.library-summary strong', dialog).textContent =
      `${current.length} 份回忆 · ${fileSize(current.reduce((sum, item) => sum + (item.size || 0), 0))}`;
    $('.library-summary p', dialog).textContent =
      `视频 ${current.filter((item) => item.kind === 'video').length} 段 · 照片 ${current.filter((item) => item.kind === 'photo').length} 张`;
  }
  dialog.innerHTML = `<header class="dialog-header"><div><h2>照顾好我们的回忆</h2><p>${local ? '原片留在原处，故事有自己的位置。' : '静态回忆库 · 修改保存在当前浏览器'}</p></div><button class="icon-button" data-close aria-label="关闭回忆库管理">${icon('close')}</button></header><div class="library-content"><div class="library-summary"><span>${icon('folder')}</span><div><strong>${items.length} 份回忆 · ${fileSize(items.reduce((sum, item) => sum + (item.size || 0), 0))}</strong><p>视频 ${items.filter((i) => i.kind === 'video').length} 段 · 照片 ${items.filter((i) => i.kind === 'photo').length} 张</p></div></div><section class="library-section"><h3>新回忆，放进来就好</h3><p>${local ? '目录中的新增或移出会自动同步，刷新页面也会立即核对。支持子文件夹，编辑记录始终保留；也可手动刷新封面。' : '当前站点读取已发布的静态索引。素材变化后，需要在素材电脑重新扫描并导出站点。'}</p>${local ? `<button class="secondary-button" id="scan-library">${icon('refresh')}刷新回忆库</button>` : ''}<p class="library-status" id="scan-message" role="status"></p></section><section class="library-section"><h3>把写下的故事，也备份一份</h3><p>备份包含你补充的日期、地点、标签、文字与珍藏状态，不含视频和照片。导入会合并记录，同一回忆以导入内容为准。</p><div class="library-actions"><button class="secondary-button" id="export-backup">${icon('download')}导出编辑记录</button><button class="secondary-button" id="import-backup">${icon('folder')}导入编辑记录</button><input type="file" id="backup-file" accept="application/json,.json" hidden></div><p class="library-status" id="import-message" role="status"></p><button class="primary-button" id="confirm-import" hidden>确认合并这份备份</button></section><section class="library-section"><h3>一起在大屏上重温</h3><p>放大回忆卡片，用遥控器方向键选择，确认键打开。照片每 8 秒翻页，视频结束后继续下一段。</p><button class="secondary-button" id="library-tv">${icon('tv')}进入客厅放映室</button></section></div>`;
  $('[data-close]', dialog).onclick = () => dialog.close();
  if (local) {
    const placement = document.createElement('section');
    placement.className = 'library-section storage-location';
    placement.hidden = true;
    placement.innerHTML =
      '<h3>新素材放在这里</h3><p class="storage-path"></p><p>在这个目录内按“年份 / 月份”存放，日期不明的放进“日期待补”。地点和主题用标签分类，不必重复复制原片。</p><details><summary>索引、标注与封面的位置</summary><p class="storage-data-path"></p><p>完整备份请保留原片、标注 memories.json 和身份映射 identities.json。</p></details>';
    $('.library-summary', dialog).after(placement);
    scanStatus()
      .then((status) => {
        if (!status.storage || !placement.isConnected) return;
        $('.storage-path', placement).textContent = status.storage.mediaRoot;
        $('.storage-data-path', placement).textContent = status.storage.dataRoot;
        placement.hidden = false;
      })
      .catch(() => {});
  }
  $('#library-tv', dialog).onclick = () => {
    dialog.close();
    enterTV();
  };
  $('#export-backup', dialog).onclick = async () => {
    try {
      downloadJSON(
        await backup(),
        `memoir-tv编辑记录-${new Date().toISOString().slice(0, 10)}.json`,
      );
      toast('回忆记录已导出，请妥善保存');
    } catch (error) {
      toast(error.message);
    }
  };
  $('#import-backup', dialog).onclick = () => $('#backup-file', dialog).click();
  let pending;
  $('#backup-file', dialog).onchange = async (event) => {
    try {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 4 * 1024 * 1024) throw new Error('备份不能超过 4 MB');
      pending = JSON.parse(await file.text());
      if (pending.version !== 1 || !pending.memories || typeof pending.memories !== 'object')
        throw new Error('不是有效的 memoir-tv 备份');
      $('#import-message', dialog).textContent =
        `将合并 ${Object.keys(pending.memories).length} 条编辑记录，请确认。`;
      $('#confirm-import', dialog).hidden = false;
    } catch (error) {
      pending = null;
      $('#confirm-import', dialog).hidden = true;
      $('#import-message', dialog).textContent = error.message;
    }
  };
  $('#confirm-import', dialog).onclick = async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await importBackup(pending);
      updateSummary(await refresh());
      button.hidden = true;
      $('#import-message', dialog).textContent = '已合并备份，回忆流已更新。';
      toast('编辑记录已恢复');
    } catch (error) {
      $('#import-message', dialog).textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  if (local)
    $('#scan-library', dialog).onclick = async (event) => {
      const button = event.currentTarget,
        message = $('#scan-message', dialog);
      button.disabled = true;
      message.textContent = '正在寻找新回忆并准备封面，大文件可能需要一点时间…';
      try {
        await startScan();
        const poll = async () => {
          try {
            const status = await scanStatus();
            if (status.running) {
              setTimeout(poll, 1600);
              return;
            }
            button.disabled = false;
            if (status.error) throw new Error(status.error);
            updateSummary(await refresh());
            message.textContent = '刷新完成，回忆列表已与素材目录同步。';
            toast('回忆库已刷新');
          } catch (error) {
            message.textContent = error.message;
            button.disabled = false;
          }
        };
        setTimeout(poll, 1200);
      } catch (error) {
        message.textContent = error.message;
        button.disabled = false;
      }
    };
  openDialog(dialog);
}
