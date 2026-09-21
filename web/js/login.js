/* Author: donglixiao · Login, registration and one-time owner setup. */
import { accountRequest } from './session.js';
import './access-navigation.js';
const form = document.querySelector('#entry-form');
const message = document.querySelector('#entry-message');
let mode = 'login';
function select(next) {
  mode = next;
  document.querySelector('#entry-title').textContent =
    next === 'setup' ? '建立你的家庭空间' : next === 'register' ? '成为回忆的一部分' : '欢迎回家';
  document.querySelector('#entry-hint').textContent =
    next === 'setup'
      ? '使用本机初始化码，创建唯一的超级管理员。'
      : next === 'register'
        ? '创建普通账号，浏览向你开放的回忆。'
        : '登录后，继续翻阅属于你的回忆。';
  document.querySelector('#phone-field').hidden = next === 'login';
  document.querySelector('#setup-field').hidden = next !== 'setup';
  form.elements.code.required = next === 'setup';
  document.querySelector('#password-hint').hidden = next === 'login';
  form.elements.password.autocomplete = next === 'login' ? 'current-password' : 'new-password';
  form.elements.password.minLength = next === 'login' ? 1 : 12;
  document.querySelector('#login-tab').setAttribute('aria-pressed', next === 'login');
  document.querySelector('#register-tab').setAttribute('aria-pressed', next === 'register');
  form.querySelector('[type=submit]').textContent =
    next === 'setup' ? '创建超级管理员' : next === 'register' ? '注册并进入' : '进入回忆';
  message.textContent = '';
}
document.querySelector('#login-tab').onclick = () => select('login');
document.querySelector('#register-tab').onclick = () => select('register');
form.onsubmit = async (event) => {
  event.preventDefault();
  const button = form.querySelector('[type=submit]');
  button.disabled = true;
  message.textContent = '正在确认账号…';
  try {
    await accountRequest(`/api/auth/${mode}`, 'POST', Object.fromEntries(new FormData(form)));
    location.replace('/');
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
try {
  const status = await accountRequest('/api/auth/me');
  if (status.user) location.replace('/');
  else if (status.setupRequired) {
    select('setup');
    document.querySelector('.access-tabs').hidden = true;
  } else {
    document.querySelector('#register-tab').hidden = !status.registration;
    if (new URLSearchParams(location.search).has('expired'))
      message.textContent = '登录已失效，请重新登录。';
  }
} catch (error) {
  message.textContent = error.message;
}
