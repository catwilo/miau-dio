// Fetch/XHR shim -- rewrites known remote hosts to /shim/<host>/<path>.
// Injected before any other script so the page never reaches the network.
(function () {
  var NATIVE_FETCH = window.fetch.bind(window);
  var SHIM_HOSTS = __SHIM_HOSTS__;
  function rewrite(url) {
    for (var i = 0; i < SHIM_HOSTS.length; i++) {
      var host = SHIM_HOSTS[i];
      var prefixes = ['https://' + host + '/', 'http://' + host + '/'];
      for (var j = 0; j < prefixes.length; j++) {
        if (url.indexOf(prefixes[j]) === 0) {
          return '/shim/' + host + '/' + url.slice(prefixes[j].length);
        }
      }
    }
    return null;
  }
  window.fetch = function (input, init) {
    var url = null;
    try { url = (typeof input === 'string') ? input : (input && input.url); }
    catch (e) { url = null; }
    if (url) {
      var r = rewrite(url);
      if (r) {
        if (typeof input === 'string') return NATIVE_FETCH(r, init);
        return NATIVE_FETCH(new Request(r, input), init);
      }
    }
    return NATIVE_FETCH(input, init);
  };
  var NativeXHR = window.XMLHttpRequest;
  window.XMLHttpRequest = function () {
    var xhr = new NativeXHR();
    var nativeOpen = xhr.open.bind(xhr);
    xhr.open = function (method, url) {
      if (typeof url === 'string') { var r = rewrite(url); if (r) url = r; }
      return nativeOpen.apply(null, arguments);
    };
    return xhr;
  };
})();
