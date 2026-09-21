/* Author: donglixiao. Classic bootstrap that can report failures on old WebViews. */
(function () {
  var entry = document.currentScript.getAttribute('data-entry');
  var legacy = false;
  try {
    new Function('var v={}; return v?.x ?? 1;');
  } catch (_) {
    legacy = true;
  }
  if (location.search.indexOf('compat=1') >= 0) legacy = true;
  if (legacy) {
    document.documentElement.classList.add('legacy-browser');
    // Some embedded WebViews calculate vh against their initial zero-height layout.
    var syncViewport = function () {
      document.documentElement.style.setProperty(
        '--legacy-height',
        Math.max(1, window.innerHeight) + 'px',
      );
    };
    syncViewport();
    window.addEventListener('resize', syncViewport);
    window.addEventListener('load', syncViewport);
  }
  if (!Object.fromEntries)
    Object.fromEntries = function (entries) {
      var value = {};
      Array.from(entries).forEach(function (pair) {
        Object.defineProperty(value, pair[0], {
          value: pair[1],
          enumerable: true,
          writable: true,
          configurable: true,
        });
      });
      return value;
    };
  if (!Element.prototype.replaceChildren)
    Element.prototype.replaceChildren = function () {
      while (this.firstChild) this.removeChild(this.firstChild);
      for (var i = 0; i < arguments.length; i++)
        this.appendChild(
          typeof arguments[i] === 'string' ? document.createTextNode(arguments[i]) : arguments[i],
        );
    };
  function report(reason) {
    if (document.getElementById('compat-error')) return;
    var box = document.createElement('aside');
    box.id = 'compat-error';
    box.setAttribute('role', 'alert');
    box.style.cssText =
      'position:fixed;z-index:2147483647;left:16px;right:16px;bottom:16px;padding:20px;background:#fff8e5;color:#40351d;border:2px solid #ab812a;border-radius:12px;font:16px/1.6 sans-serif';
    var text = document.createElement('p');
    text.textContent = 'memoir-tv 页面启动失败：' + reason + '。内核：' + navigator.userAgent;
    var button = document.createElement('button');
    button.textContent = '重新加载';
    button.style.cssText = 'padding:12px 24px;font-size:18px';
    button.onclick = function () {
      location.reload();
    };
    box.appendChild(text);
    box.appendChild(button);
    document.body.appendChild(box);
    button.focus();
  }
  window.addEventListener('error', function (event) {
    if (!window.memoirReady && event.message) report(event.message);
  });
  var script = document.createElement('script');
  if (!legacy) script.type = 'module';
  script.src = legacy ? './compat/' + entry + '.js' : './js/' + entry + '.js';
  script.onerror = function () {
    report('无法加载 ' + script.src);
  };
  document.head.appendChild(script);
  setTimeout(function () {
    if (!window.memoirReady) report('脚本 15 秒内未就绪，请检查网络或升级 Android System WebView');
  }, 15000);
})();
