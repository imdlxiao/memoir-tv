/* Author: donglixiao · Direction-key focus for account screens on televisions. */
document.addEventListener('keydown', (event) => {
  if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
  const controls = [...document.querySelectorAll('a[href], button, input, select')].filter(
    (element) => !element.disabled && element.getClientRects().length,
  );
  const current = controls.indexOf(document.activeElement);
  const delta = ['ArrowUp', 'ArrowLeft'].includes(event.key) ? -1 : 1;
  const next =
    controls[current < 0 ? 0 : Math.max(0, Math.min(controls.length - 1, current + delta))];
  if (next) {
    event.preventDefault();
    next.focus();
  }
});
