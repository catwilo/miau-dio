// Preload vendored Strudel sample packs at REPL start.
// Reads window.__MIAU_PRELOAD__ (list of manifest URLs, injected by
// server.py from --samples). Waits for the REPL's samples() function
// to exist, then loads each URL once. No-op when the list is empty.
(function () {
  var urls = window.__MIAU_PRELOAD__ || [];
  if (!urls.length) return;
  var tries = 0;
  var iv = setInterval(function () {
    tries++;
    if (tries > 150) { clearInterval(iv); return; }
    if (typeof window.samples !== 'function') return;
    clearInterval(iv);
    for (var i = 0; i < urls.length; i++) {
      try { window.samples(urls[i]); } catch (e) {}
    }
  }, 200);
})();
