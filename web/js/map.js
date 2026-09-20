/* Author: donglixiao · Private photo atlas, clustered covers and manual pin selection. */
import { $, escapeHTML as e, titleOf, dateLabel, safeURL, openDialog, toast } from './utils.js';
import { icon } from './icons.js';
import { validCoordinates, latLng, clusterPoints } from './geo.js';

let leafletPromise,
  landPromise,
  session = 0;
function leaflet() {
  if (!leafletPromise)
    leafletPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = new URL('../vendor/leaflet/leaflet.js', import.meta.url).href;
      script.onload = () => resolve(window.L);
      script.onerror = () => {
        leafletPromise = null;
        script.remove();
        reject(new Error('地图组件未能加载，请刷新后重试'));
      };
      document.head.append(script);
    });
  return leafletPromise;
}
function land() {
  if (!landPromise)
    landPromise = fetch(new URL('../vendor/natural-earth/land.geojson', import.meta.url))
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .catch(() => {
        landPromise = null;
        return null;
      });
  return landPromise;
}
const cover = (item) =>
  item.thumbnail
    ? `<img src="${e(safeURL(item.thumbnail))}" alt="" loading="lazy">`
    : `<span class="map-cover-fallback">${icon(item.kind === 'video' ? 'video' : 'image')}</span>`;

export async function openMap(items, { focusId, onOpen, onEdit, onPick, initial } = {}) {
  const dialog = $('#map-dialog');
  if (dialog.open) return;
  const currentSession = ++session;
  dialog.addEventListener(
    'close',
    () => {
      if (session === currentSession) session++;
    },
    { once: true },
  );
  dialog.innerHTML = '<div class="map-loading" role="status">正在展开回忆地图…</div>';
  openDialog(dialog);
  let L;
  try {
    L = await leaflet();
  } catch (error) {
    dialog.close();
    toast(error.message);
    return;
  }
  if (!dialog.open || session !== currentSession) return;
  const located = items.filter((item) => validCoordinates(item.coordinates));
  const missing = items.filter((item) => !validCoordinates(item.coordinates));
  const focus = located.find((item) => item.id === focusId);
  const picking = typeof onPick === 'function';
  let nearby = !focus,
    picked = validCoordinates(initial) ? initial : null,
    disposed = false;
  let tiles,
    pin,
    tileErrors = 0,
    tileLoaded = 0;
  dialog.innerHTML = `<header class="atlas-header"><div><span class="atlas-eyebrow">MEMOIR-TV / PLACES</span><h2>${picking ? '给回忆一个位置' : '我们走过的地方'}</h2></div><button class="atlas-round" data-map-close aria-label="关闭回忆地图">${icon('close')}</button></header>
    <div class="atlas-body"><div id="memory-map" aria-label="回忆地图，方向键移动，加减号缩放" tabindex="0"></div>
    <div class="atlas-controls"><button class="atlas-round" data-map-fit aria-label="查看全部地点">${icon('expand')}</button><button class="atlas-round" data-map-in aria-label="放大地图">＋</button><button class="atlas-round" data-map-out aria-label="缩小地图">−</button></div>
    <div class="atlas-basemap"><button data-map-tiles>${icon('map')}加载街道地图</button><span data-map-status role="status">离线概览 · 无需 Key</span><small data-map-privacy>加载街道后，会向 OpenStreetMap 请求当前区域底图；照片不会上传。</small></div>
    <section class="atlas-sheet" aria-label="地图中的回忆"><div class="atlas-sheet-head"><div><strong data-map-count></strong><p data-map-caption></p></div>${picking ? '' : `<button class="atlas-chip" data-map-nearby ${focus ? '' : 'hidden'} aria-pressed="false">显示附近回忆</button><button class="atlas-chip" data-map-missing ${missing.length ? '' : 'hidden'}>待补位置 ${missing.length}</button>`}</div><div class="atlas-items"></div>${picking ? '<div class="atlas-pick"><p data-picked role="status">点击地图，或移动地图后选择中心点。</p><button class="secondary-button" data-pick-center>选择地图中心</button><button class="primary-button" data-pick-save disabled>使用这个位置</button></div>' : ''}</section>
    </div>`;
  const map = L.map($('#memory-map'), {
    zoomControl: false,
    attributionControl: true,
    minZoom: 2,
    maxZoom: 19,
    worldCopyJump: false,
    maxBounds: [
      [-85.0511, -180],
      [85.0511, 180],
    ],
    maxBoundsViscosity: 1,
    zoomAnimation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
  });
  const pins = L.layerGroup().addTo(map);
  const boundsOf = (list) => L.latLngBounds(list.map(latLng));
  const framing = () => ({
    paddingTopLeft: [
      60,
      Math.min(
        map.getSize().y * 0.4,
        $('.atlas-basemap', dialog).offsetTop + $('.atlas-basemap', dialog).offsetHeight + 100,
      ),
    ],
    paddingBottomRight: [
      100,
      Math.min(map.getSize().y * 0.35, $('.atlas-sheet', dialog).offsetHeight + 65),
    ],
    animate: false,
  });
  const fit = () => {
    if (picking && picked) map.setView([picked.latitude, picked.longitude], 14);
    else if (located.length)
      map.fitBounds(boundsOf(located), {
        ...framing(),
        maxZoom: 15,
      });
    else map.setView([27, 108], 4);
  };
  const updateStats = () => {
    const count = located.filter((item) => map.getBounds().contains(latLng(item))).length;
    $('[data-map-count]', dialog).textContent = picking
      ? '在地图上轻点，标记当时的位置'
      : `${nearby ? count : focus ? 1 : 0} 份回忆，在这片风景里`;
    $('[data-map-caption]', dialog).textContent = picking
      ? '保存到回忆记录，不改写原片。坐标使用 WGS84。'
      : `${located.length} 份有位置 · ${missing.length} 份待补位置 · 沿用当前列表筛选`;
  };
  function showItems(list, unlocated = false) {
    const tray = $('.atlas-items', dialog);
    tray.innerHTML = list.length
      ? `${list.length > 1 && !unlocated ? '<button class="atlas-chip" data-map-spread>展开这些地点</button>' : ''}` +
        list
          .slice(0, 100)
          .map(
            (item) =>
              `<article class="atlas-memory"><button data-map-open="${e(item.id)}" aria-label="查看 ${e(titleOf(item))}">${cover(item)}<span><strong>${e(titleOf(item))}</strong><small>${e(item.location || (unlocated ? '还没有拍摄坐标' : dateLabel(item)))}</small></span></button>${onEdit ? `<button class="atlas-edit" data-map-edit="${e(item.id)}" aria-label="调整 ${e(titleOf(item))} 的位置">${icon('edit')}</button>` : ''}</article>`,
          )
          .join('') +
        (list.length > 100 ? '<p>先展示 100 份，请缩小地图范围或使用首页筛选。</p>' : '')
      : `<div class="atlas-empty">${icon('pin')}<strong>还没有留下坐标的回忆</strong><p>原片带 GPS 时会自动出现在这里。也可以在“编辑回忆”中选点，补上当时的位置。</p></div>`;
    $('[data-map-spread]', tray)?.addEventListener('click', () =>
      map.fitBounds(boundsOf(list), {
        ...framing(),
        maxZoom: 19,
      }),
    );
    tray.querySelectorAll('[data-map-open]').forEach(
      (button) =>
        (button.onclick = () => {
          if (!onOpen) return;
          const id = button.dataset.mapOpen;
          dialog.close();
          onOpen(list, id);
        }),
    );
    tray.querySelectorAll('[data-map-edit]').forEach(
      (button) =>
        (button.onclick = () => {
          const item = items.find((item) => item.id === button.dataset.mapEdit);
          dialog.close();
          onEdit(item);
        }),
    );
  }
  function renderPins() {
    if (disposed || picking) return;
    pins.clearLayers();
    updateStats();
    const visible = (nearby ? located : focus ? [focus] : []).filter((item) =>
      map.getBounds().pad(0.15).contains(latLng(item)),
    );
    const groups = clusterPoints(
      visible,
      (item) => map.latLngToContainerPoint(latLng(item)),
      innerWidth < 600 ? 76 : 92,
    );
    for (const group of groups) {
      const item = group.items[0],
        size = innerWidth < 600 ? 64 : 80;
      const marker = L.marker(latLng(item), {
        keyboard: true,
        title: `${item.location || titleOf(item)} · ${group.items.length} 份回忆`,
        alt: `查看 ${group.items.length} 份回忆`,
        icon: L.divIcon({
          className: 'photo-pin',
          iconSize: [size, size],
          iconAnchor: [size / 2, size + 8],
          html: `<span class="photo-pin-frame">${cover(item)}<b>${group.items.length > 1 ? group.items.length : item.kind === 'video' ? icon('play') : ''}</b></span>`,
        }),
      }).addTo(pins);
      marker.on('click', () => showItems(group.items));
    }
  }
  const choose = (position) => {
    picked = {
      latitude: Number(Math.max(-90, Math.min(90, position.lat)).toFixed(6)),
      longitude: Number(Math.max(-180, Math.min(180, position.lng)).toFixed(6)),
    };
    if (pin) pin.setLatLng([picked.latitude, picked.longitude]);
    else
      pin = L.circleMarker([picked.latitude, picked.longitude], {
        pane: 'markerPane',
        radius: 12,
        color: '#fff',
        weight: 4,
        fillColor: '#496d51',
        fillOpacity: 1,
      }).addTo(map);
    $('[data-picked]', dialog).textContent =
      `${picked.latitude.toFixed(6)}，${picked.longitude.toFixed(6)}`;
    $('[data-pick-save]', dialog).disabled = false;
  };
  $('[data-map-close]', dialog).onclick = () => dialog.close();
  $('[data-map-fit]', dialog).onclick = fit;
  $('[data-map-in]', dialog).onclick = () => map.zoomIn();
  $('[data-map-out]', dialog).onclick = () => map.zoomOut();
  $('[data-map-nearby]', dialog)?.addEventListener('click', (event) => {
    nearby = !nearby;
    event.currentTarget.textContent = nearby ? '隐藏附近回忆' : '显示附近回忆';
    event.currentTarget.setAttribute('aria-pressed', nearby);
    renderPins();
  });
  $('[data-map-missing]', dialog)?.addEventListener('click', () => showItems(missing, true));
  $('[data-map-tiles]', dialog).onclick = () => {
    const button = $('[data-map-tiles]', dialog),
      status = $('[data-map-status]', dialog);
    if (tiles) {
      map.removeLayer(tiles);
      tiles = null;
      button.innerHTML = `${icon('map')}加载街道地图`;
      status.textContent = '离线概览 · 无需 Key';
      return;
    }
    tileErrors = 0;
    tileLoaded = 0;
    tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      noWrap: true,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>',
    });
    tiles.on('tileload', () => {
      tileLoaded++;
      status.textContent = tileErrors
        ? '部分街道未加载，可重试或切回离线'
        : '街道地图 · OpenStreetMap';
    });
    tiles.on('tileerror', () => {
      tileErrors++;
      status.textContent = tileLoaded
        ? '部分街道未加载，可重试或切回离线'
        : '街道暂时无法加载，可切回离线';
    });
    tiles.addTo(map);
    button.innerHTML = `${icon('map')}切回离线概览`;
    status.textContent = '正在加载街道…';
  };
  if (picking) {
    map.on('click', (event) => choose(event.latlng));
    $('[data-pick-center]', dialog).onclick = () => choose(map.getCenter());
    $('[data-pick-save]', dialog).onclick = () => {
      dialog.close();
      onPick(picked);
    };
  }
  map.on('moveend', renderPins);
  map.on('resize', () => {
    if (picking) return;
    if (focus && !nearby)
      map.fitBounds(boundsOf([focus]), { ...framing(), maxZoom: map.getZoom() });
    else fit();
  });
  dialog.addEventListener(
    'close',
    () => {
      disposed = true;
      map.remove();
    },
    { once: true },
  );
  map.invalidateSize();
  $('[data-map-close]', dialog).focus({ preventScroll: true });
  if (focus && !picking) map.setView(latLng(focus), 14);
  else fit();
  if (picking) {
    updateStats();
    if (picked) choose({ lat: picked.latitude, lng: picked.longitude });
  } else {
    renderPins();
    if (focus) showItems([focus]);
    else if (!located.length) showItems(missing, true);
  }
  land().then((data) => {
    if (disposed || !data) return;
    L.geoJSON(data, {
      pane: 'overlayPane',
      interactive: false,
      style: { color: '#a4b99a', weight: 1, fillColor: '#e4ecd3', fillOpacity: 1 },
    })
      .addTo(map)
      .bringToBack();
    // Raster tiles belong above the coarse offline land, but below photo pins.
    map.getPane('tilePane').style.zIndex = '450';
    map.attributionControl.addAttribution(
      '<a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a>',
    );
  });
}
