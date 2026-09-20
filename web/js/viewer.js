/* Author: donglixiao · Accessible photo/video theater and remote navigation. */
import {icon} from './icons.js';
import {$, escapeHTML as e, titleOf, dateLabel, mediaURL, openDialog, toast} from './utils.js';
let playlist = [], index = 0, slideshow = null;
function stopSlideshow() { clearTimeout(slideshow); slideshow = null; }
function render() {
  stopSlideshow();
  const dialog = $('#viewer-dialog'), item = playlist[index];
  const previous = $('video',dialog); if (previous) { previous.pause(); previous.removeAttribute('src'); previous.load(); }
  dialog.innerHTML = `<header class="viewer-toolbar"><div><h2>${e(titleOf(item))}</h2><p>${e(dateLabel(item))}${item.location ? ` · ${e(item.location)}` : ''}</p></div><div class="viewer-tools"><button class="icon-button" data-fullscreen aria-label="全屏播放">${icon('expand')}</button><button class="icon-button" data-close aria-label="关闭放映室">${icon('close')}</button></div></header><div class="viewer-media">${item.kind === 'video' ? `<video controls playsinline preload="metadata" src="${e(mediaURL(item))}" ${item.thumbnail ? `poster="${e(new URL(item.thumbnail,location.href).href)}"` : ''}></video>` : `<img src="${e(mediaURL(item))}" alt="${e(titleOf(item))}">`}</div><footer class="viewer-footer"><button data-previous ${index === 0 ? 'disabled' : ''}>${icon('left')}上一段</button><span>${index + 1} / ${playlist.length} <span class="viewer-hint"> · ← → 切换 · Esc 返回</span></span><button data-next ${index === playlist.length-1 ? 'disabled' : ''}>下一段${icon('right')}</button></footer>`;
  $('[data-close]',dialog).onclick=()=>dialog.close();
  $('[data-previous]',dialog).onclick=()=>navigate(-1);
  $('[data-next]',dialog).onclick=()=>navigate(1);
  $('[data-fullscreen]',dialog).onclick=async()=>{ try { if (document.fullscreenElement) await document.exitFullscreen(); else if (dialog.requestFullscreen) await dialog.requestFullscreen(); else if ($('video',dialog)?.webkitEnterFullscreen) $('video',dialog).webkitEnterFullscreen(); else toast('当前浏览器不支持全屏，请使用播放器全屏按钮'); } catch { toast('当前浏览器未允许全屏'); } };
  const media = $('video,img', $('.viewer-media',dialog));
  media.addEventListener('error',()=>{ const container = $('.viewer-media',dialog); container.innerHTML=`<div class="viewer-error"><p>浏览器暂时无法打开这份原片。部分 MOV、HEVC、HEIC 格式需要设备解码支持，可以下载后用本地播放器查看。</p><a href="${e(mediaURL(item))}" download="${e(item.filename)}">${item.kind === 'video' ? '下载视频原片' : '下载照片原片'}</a></div>`; });
  if (item.kind === 'video') media.addEventListener('ended',()=>{ if(document.body.classList.contains('tv-mode')) navigate(1); });
  else if (document.body.classList.contains('tv-mode')) slideshow=setTimeout(()=>navigate(1),8000);
  if (dialog.open) $('[data-next]',dialog).focus({preventScroll:true});
}
function navigate(delta) { const next = index + delta; if (next < 0 || next >= playlist.length) return; index=next; render(); if (document.body.classList.contains('tv-mode')) $('video', $('#viewer-dialog'))?.play().catch(()=>{}); }
export function openViewer(items, id) { playlist=items; index=Math.max(0,items.findIndex(item=>item.id===id)); if (!playlist.length) return; render(); openDialog($('#viewer-dialog')); $('video', $('#viewer-dialog'))?.play().catch(()=>{}); }
export function initializeViewer() { const dialog=$('#viewer-dialog'); dialog.addEventListener('close',()=>{ stopSlideshow(); const video=$('video',dialog); if(video) {video.pause(); video.removeAttribute('src');video.load();} if(document.fullscreenElement) document.exitFullscreen().catch(()=>{}); }); dialog.addEventListener('keydown',event=>{ if(event.target.tagName==='VIDEO') return; if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();navigate(event.key==='ArrowLeft'?-1:1);} }); }
