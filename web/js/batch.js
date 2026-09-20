/* Author: donglixiao · Explicit multi-selection and atomic metadata editing. */
import { $, openDialog, toast } from './utils.js';
import { icon } from './icons.js';
import { state, filteredItems } from './store.js';
import { saveBatch, getMode } from './api.js';

export function renderSelection() {
  const valid = new Set(state.items.map((item) => item.id));
  for (const id of state.selected) if (!valid.has(id)) state.selected.delete(id);
  $('#batch-toolbar').hidden = !state.selecting;
  $('#batch-toggle').setAttribute('aria-pressed', state.selecting);
  $('#selection-count').textContent = `已选 ${state.selected.size} 条`;
  $('#batch-edit').disabled = !state.selected.size;
  for (const card of document.querySelectorAll('.memory-card')) {
    card.classList.toggle('selected', state.selected.has(card.dataset.id));
    if (!state.selecting) continue;
    const button = document.createElement('button');
    button.className = 'selection-control';
    button.dataset.action = 'select';
    button.setAttribute('aria-label', `选择${$('.card-title', card).textContent}`);
    button.setAttribute('aria-pressed', state.selected.has(card.dataset.id));
    button.innerHTML = state.selected.has(card.dataset.id) ? '✓' : '+';
    $('.card-header', card).prepend(button);
  }
}

export function toggleSelection(id, redraw) {
  if (state.selected.has(id)) state.selected.delete(id);
  else if (state.selected.size >= 200) {
    toast('每次最多整理 200 条，可分批完成');
    return;
  } else state.selected.add(id);
  redraw();
}

export function initializeBatch(redraw, refresh) {
  const finish = () => {
    state.selecting = false;
    state.selected.clear();
    redraw();
  };
  $('#batch-toggle').onclick = () => {
    state.selecting = !state.selecting;
    if (!state.selecting) state.selected.clear();
    redraw();
  };
  $('#batch-cancel').onclick = finish;
  $('#select-page').onclick = () => {
    for (const item of filteredItems().slice(0, state.limit)) {
      if (state.selected.size >= 200) break;
      state.selected.add(item.id);
    }
    redraw();
  };
  $('#clear-selection').onclick = () => {
    state.selected.clear();
    redraw();
  };
  $('#batch-edit').onclick = () => openBatchEditor(refresh, finish);
}

function openBatchEditor(refresh, finish) {
  const dialog = $('#batch-dialog'),
    ids = [...state.selected];
  if (!ids.length) return;
  dialog.innerHTML = `<header class="dialog-header"><div><h2>一起整理这 ${ids.length} 段回忆</h2><p>只修改勾选的字段，其他记录保持原样。</p></div><button class="icon-button" data-close aria-label="关闭批量整理">${icon('close')}</button></header>
    <form class="editor-form">
      <label class="batch-field-toggle"><input type="checkbox" name="applyDate">统一拍摄日期</label>
      <fieldset data-field="date" disabled class="batch-fields"><div class="form-row"><label class="form-field">记得多具体<select name="precision"><option value="month">大约某个月</option><option value="day">记得哪一天</option><option value="unknown">清除日期</option></select></label><label class="form-field">拍摄日期<input type="month" name="date" required pattern="[0-9]{4}-[0-9]{2}" placeholder="YYYY-MM"></label></div></fieldset>
      <label class="batch-field-toggle"><input type="checkbox" name="applyLocation">统一地点</label>
      <fieldset data-field="location" disabled class="batch-fields"><label class="form-field">回忆发生地<input name="location" maxlength="100" list="known-places" placeholder="例如：杭州 · 外婆家；留空可清除地点"></label></fieldset>
      <label class="batch-field-toggle"><input type="checkbox" name="applyTags">整理标签</label>
      <fieldset data-field="tags" disabled class="batch-fields"><div class="form-row"><label class="form-field">操作<select name="tagMode"><option value="append">追加标签</option><option value="replace">替换全部标签</option><option value="remove">移除指定标签</option></select></label><label class="form-field">标签<input name="tags" placeholder="家人，旅行，夏天"></label></div></fieldset>
      <label class="batch-field-toggle"><input type="checkbox" name="applyFavorite">统一珍藏状态</label>
      <fieldset data-field="favorite" disabled class="batch-fields"><label class="form-field">珍藏<select name="favorite"><option value="true">加入珍藏</option><option value="false">取消珍藏</option></select></label></fieldset>
      <p class="form-hint">标签默认追加，不覆盖已有标签。每条最多 20 个标签。${getMode() === 'static' ? '修改保存在当前浏览器，请及时导出备份。' : '全部验证通过后一次保存，写入前自动备份。'}</p>
      <p class="form-error" role="alert" hidden></p><footer class="form-footer"><button class="secondary-button" type="button" data-close>取消</button><button class="primary-button" type="submit">保存 ${ids.length} 条回忆</button></footer>
    </form>`;
  const form = $('form', dialog);
  for (const [name, field] of [
    ['applyDate', 'date'],
    ['applyLocation', 'location'],
    ['applyTags', 'tags'],
    ['applyFavorite', 'favorite'],
  ])
    form.elements[name].onchange = () => {
      $(`[data-field="${field}"]`, form).disabled = !form.elements[name].checked;
    };
  form.elements.precision.onchange = () => {
    const precision = form.elements.precision.value,
      date = form.elements.date;
    date.type = precision === 'month' ? 'month' : 'date';
    date.disabled = precision === 'unknown';
    date.required = !date.disabled;
    date.pattern = precision === 'month' ? '[0-9]{4}-[0-9]{2}' : '[0-9]{4}-[0-9]{2}-[0-9]{2}';
  };
  dialog
    .querySelectorAll('[data-close]')
    .forEach((button) => (button.onclick = () => dialog.close()));
  form.onsubmit = async (event) => {
    event.preventDefault();
    const fields = form.elements,
      changes = {},
      error = $('.form-error', form),
      submit = $('[type=submit]', form);
    error.hidden = true;
    if (fields.applyDate.checked) {
      changes.precision = fields.precision.value;
      changes.date = changes.precision === 'unknown' ? '' : fields.date.value;
    }
    if (fields.applyLocation.checked) changes.location = fields.location.value.trim();
    if (fields.applyTags.checked)
      changes.tags = [
        ...new Set(
          fields.tags.value
            .split(/[,，;；\n]/)
            .map((t) => t.trim().replace(/^#+/, ''))
            .filter(Boolean),
        ),
      ];
    if (fields.applyFavorite.checked) changes.favorite = fields.favorite.value === 'true';
    submit.disabled = true;
    try {
      const result = await saveBatch(ids, changes, fields.tagMode.value);
      await refresh();
      dialog.close();
      finish();
      toast(`已整理 ${result.count} 条回忆`);
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  };
  openDialog(dialog);
}
