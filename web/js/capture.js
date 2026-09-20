/* Author: donglixiao · Original camera facts, distinct from editable memory annotations. */
import { escapeHTML as e, fileSize } from './utils.js';
import { icon } from './icons.js';
import { validCoordinates } from './geo.js';

export function captureHTML(item) {
  const info = item.capture || {};
  const device = info.model?.toLowerCase().startsWith((info.make || '\0').toLowerCase())
    ? info.model
    : [info.make, info.model].filter(Boolean).join(' ');
  const resolution =
    info.width && info.height
      ? `${info.width} × ${info.height} · ${((info.width * info.height) / 1000000).toFixed(1)} MP`
      : '';
  const parameters = [
    ['ISO', info.iso],
    ['焦距', info.focalLength ? `${info.focalLength} mm` : null],
    ['光圈', info.aperture ? `ƒ/${info.aperture}` : null],
    [
      '曝光时间',
      info.exposure > 0
        ? info.exposure < 1
          ? `1/${Math.round(1 / info.exposure)} s`
          : `${info.exposure} s`
        : null,
    ],
    ['曝光补偿', info.exposureBias != null ? `${info.exposureBias} ev` : null],
    [
      '视频时长',
      info.duration > 0
        ? `${Math.floor(info.duration / 60)}:${String(Math.round(info.duration % 60)).padStart(2, '0')}`
        : null,
    ],
    ['帧率', info.frameRate > 0 ? `${Number(info.frameRate.toFixed(2))} fps` : null],
  ].filter(([, value]) => value != null);
  const coordinates = validCoordinates(item.coordinates);
  return `<section class="capture-card" aria-label="原始拍摄参数"><div class="capture-heading"><strong>${e(device || info.model || '原始文件信息')}</strong><span>${e(info.format || item.filename.split('.').pop().toUpperCase())}</span></div>${info.lens ? `<p>${e(info.lens)}</p>` : ''}<p>${e([resolution, fileSize(item.size || 0)].filter(Boolean).join(' · '))}</p>${info.takenAt ? `<p>原片记录时间 · ${e(info.takenAt.replace('T', ' '))}</p>` : '<p>原片没有可识别的拍摄时间，回忆日期可单独调整。</p>'}${parameters.length ? `<div class="capture-values">${parameters.map(([label, value]) => `<span><small>${label}</small>${e(value)}</span>`).join('')}</div>` : '<p>原片没有保留可识别的相机参数。</p>'}</section>
    <button class="capture-location" data-capture-map>${icon('map')}<span><strong>${e(item.location || (coordinates ? '回到拍摄的地方' : '这段回忆，发生在哪里'))}</strong><small>${coordinates ? '在地图上查看 · 发现附近的回忆' : '还没有 GPS 坐标 · 点击补充位置'}</small></span>${icon('right')}</button><button class="quiet-button" data-capture-edit>${icon('edit')}调整日期、位置与标签</button>`;
}
