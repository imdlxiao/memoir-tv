/* Author: donglixiao · Session transport and expiry handling. */
export async function accountRequest(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    credentials: 'same-origin',
    cache: 'no-store',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401 && !location.pathname.endsWith('/login.html')) {
    location.replace('/login.html?expired=1');
  }
  if (!response.ok) throw new Error(result.error || `请求失败 (${response.status})`);
  return result;
}

export function watchSession(onChange) {
  let busy = false;
  let revision;
  const check = async () => {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const result = await accountRequest('/api/auth/me');
      if (!result.user) {
        document.querySelectorAll('video').forEach((video) => video.pause());
        location.replace('/login.html?expired=1');
      } else {
        if (revision !== undefined && revision !== result.accessRevision) onChange?.();
        revision = result.accessRevision;
      }
    } catch {
      // Transient connection loss does not discard the session.
    } finally {
      busy = false;
    }
  };
  check();
  setInterval(check, 5000);
  window.addEventListener('focus', check);
  window.addEventListener('pageshow', check);
  document.addEventListener('visibilitychange', check);
}
