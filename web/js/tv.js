/* Author: donglixiao · Spatial keyboard navigation for living-room displays. */
import {$} from './utils.js';
export function setTV(enabled) {
  document.body.classList.toggle('tv-mode',enabled);
  let exit=$('#tv-exit');
  if(enabled&&!exit){exit=document.createElement('button');exit.id='tv-exit';exit.className='tv-exit';exit.textContent='退出放映室';exit.onclick=()=>setTV(false);$('.topbar-actions').prepend(exit);}
  if(exit)exit.hidden=!enabled;
  if(enabled){window.scrollTo({top:0});setTimeout(()=>$('.media-frame')?.focus(),100);}
}
export function initializeTV() {
  document.addEventListener('keydown',event=>{
    if(!document.body.classList.contains('tv-mode'))return;
    if(document.querySelector('dialog[open]'))return;
    if(event.key==='Escape'){setTV(false);return;}
    if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)||['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName))return;
    const current=document.activeElement,rect=current.getBoundingClientRect(),cx=rect.left+rect.width/2,cy=rect.top+rect.height/2;
    const horizontal=event.key==='ArrowLeft'||event.key==='ArrowRight',sign=['ArrowLeft','ArrowUp'].includes(event.key)?-1:1;
    let best=null,score=Infinity;
    document.querySelectorAll('button:not(:disabled),a[href],input,select').forEach(candidate=>{
      if(candidate===current||!candidate.getClientRects().length||candidate.closest('dialog:not([open])'))return;
      const r=candidate.getBoundingClientRect(),dx=r.left+r.width/2-cx,dy=r.top+r.height/2-cy,along=(horizontal?dx:dy)*sign,cross=Math.abs(horizontal?dy:dx);
      if(along<=8)return;
      const rank=along+cross*3;if(rank<score){score=rank;best=candidate;}
    });
    if(best){event.preventDefault();best.focus();best.scrollIntoView({block:'nearest',behavior:'auto'});}
  });
}
