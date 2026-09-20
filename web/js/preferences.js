/* Author: donglixiao · Small validated per-browser presentation preferences. */
const KEY = 'memoir-preferences-v1';
const speeds = [0.5, 0.75, 1, 1.25, 1.5, 2],
  intervals = [5, 8, 15, 30];
export function preferences() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
  } catch {}
  return {
    speed: speeds.includes(saved.speed) ? saved.speed : 1,
    interval: intervals.includes(saved.interval) ? saved.interval : 8,
    continuous: saved.continuous === true,
    grid: saved.grid === true,
    ascending: saved.ascending === true,
  };
}
export function savePreference(key, value) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...preferences(), [key]: value }));
  } catch {
    /* Optional preferences never block the interface. */
  }
}
