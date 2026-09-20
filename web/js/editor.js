/* Author: donglixiao · Date precision and memory metadata editing. */
import { icon } from './icons.js';
import { $, escapeHTML as e, openDialog, toast } from './utils.js';
import { saveMemory, getMode } from './api.js';
export function editMemory(item, onSaved) {
  const dialog = $('#editor-dialog');
  dialog.innerHTML = `<header class="dialog-header"><div><h2>给回忆，添几笔</h2><p>记不清具体哪天？只记到月份也很好。</p></div><button class="icon-button" type="button" data-close aria-label="关闭编辑">${icon('close')}</button></header><form class="editor-form"><div class="editor-source">原片 · ${e(item.filename)}</div><label class="form-field">回忆的名字<input name="title" maxlength="120" value="${e(item.title)}" placeholder="比如：外婆家的那个夏天"></label><label class="form-field">写下当时的故事<textarea name="description" maxlength="3000" placeholder="那天和谁在一起，发生了什么小事…">${e(item.description)}</textarea></label><div class="form-row"><label class="form-field">记得多具体<select name="precision"><option value="day">记得哪一天</option><option value="month">大约某个月</option><option value="unknown">暂时想不起来</option></select></label><label class="form-field">拍摄日期<input name="date" aria-label="拍摄日期"></label></div><p class="form-hint">${item.dateSource === 'filename' ? '初始日期来自文件名，可按真实拍摄时间修正。' : '日期会保留你选择的精度，不会为月份虚构某一天。'}</p><label class="form-field">回忆发生地<input name="location" maxlength="100" value="${e(item.location)}" placeholder="比如：杭州 · 外婆家" list="known-places"></label><label class="form-field">给回忆打个标签<input name="tags" value="${e((item.tags || []).join('，'))}" placeholder="家人，旅行，生日，日常"></label><p class="form-hint">用逗号分隔，最多 20 个标签。${getMode() === 'static' ? '静态浏览模式：修改仅保存在当前浏览器，请及时导出备份。' : '保存到独立的回忆记录，不改动原片。'}</p><p class="form-error" role="alert" hidden></p><footer class="form-footer"><button type="button" class="secondary-button" data-close>先不改了</button><button type="submit" class="primary-button">${icon('leaf')}保存这段回忆</button></footer></form>`;
  const form = $('form', dialog),
    precision = form.elements.precision,
    date = form.elements.date;
  precision.value = item.precision || 'unknown';
  const syncDate = () => {
    const old = date.value || item.date || '';
    date.type = precision.value === 'month' ? 'month' : 'date';
    date.disabled = precision.value === 'unknown';
    date.required = !date.disabled;
    date.value = date.disabled
      ? ''
      : precision.value === 'month'
        ? old.slice(0, 7)
        : old.length === 10
          ? old
          : '';
    date.pattern = precision.value === 'month' ? '[0-9]{4}-[0-9]{2}' : '[0-9]{4}-[0-9]{2}-[0-9]{2}';
    date.placeholder = precision.value === 'month' ? 'YYYY-MM' : 'YYYY-MM-DD';
  };
  syncDate();
  precision.addEventListener('change', syncDate);
  dialog
    .querySelectorAll('[data-close]')
    .forEach((button) => button.addEventListener('click', () => dialog.close()));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const error = $('.form-error', dialog),
      submit = $('[type=submit]', form);
    error.hidden = true;
    const changes = {
      title: form.elements.title.value.trim(),
      description: form.elements.description.value.trim(),
      precision: precision.value,
      date: date.value,
      location: form.elements.location.value.trim(),
      tags: [
        ...new Set(
          form.elements.tags.value
            .split(/[,，;；\n]/)
            .map((t) => t.trim().replace(/^#/, ''))
            .filter(Boolean),
        ),
      ],
    };
    if (changes.tags.length > 20 || changes.tags.some((t) => t.length > 30)) {
      error.textContent = '最多 20 个标签，每个最多 30 个字。';
      error.hidden = false;
      return;
    }
    submit.disabled = true;
    try {
      await saveMemory(item.id, changes);
      Object.assign(item, changes);
      dialog.close();
      onSaved();
      toast('这段回忆，已经好好收下了');
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
  openDialog(dialog);
}
