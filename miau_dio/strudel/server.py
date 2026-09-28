"""Local Strudel server -- vendored official site + fetch shim + samples.

Scope (task #174, part of redesign #168): `miau-dio live` runs a stdlib
HTTP server on localhost that serves the **official Strudel site**
vendored into `site/` (HTML + Astro chunks + fonts + CSS), plus:

  GET /shim/<host>/<path>      -> XDG cache (samples, hydra, jzz, ...)
  GET /samples/<file>          -> user wavs under XDG
  GET /samples/index.json      -> {name: /samples/<file>}
  anything else                -> site/<path> (static)

The served index.html is the official one with a small fetch/XHR shim
injected before any <script>. Requests to known remote hosts
(raw.githubusercontent.com, cdn.jsdelivr.net, unpkg.com,
felixroos.github.io, shabda.ndre.gr) are rewritten to /shim/<host>/<path>
which the server resolves from XDG_DATA_HOME/miau-dio/strudel/cache/.
Uncached files 404, so the browser never reaches the network.

Packs are materialized into the cache by `miau-dio sample install <pack>`,
never by the browser. Nothing but the vendored site + catalog metadata
lives in git; samples are always local content.
"""
from __future__ import annotations

import http.server
import json
import os
import pathlib
import socketserver
import threading

_HERE = pathlib.Path(__file__).resolve().parent
_SITE = _HERE / "site"

_FETCH_SHIM = """<script>
(function () {
  const NATIVE_FETCH = window.fetch.bind(window);
  const SHIM_HOSTS = [
    'raw.githubusercontent.com',
    'cdn.jsdelivr.net',
    'unpkg.com',
    'felixroos.github.io',
    'shabda.ndre.gr',
  ];
  function rewrite(url) {
    for (const host of SHIM_HOSTS) {
      for (const prefix of ['https://' + host + '/', 'http://' + host + '/']) {
        if (url.startsWith(prefix)) {
          return '/shim/' + host + '/' + url.slice(prefix.length);
        }
      }
    }
    return null;
  }
  window.fetch = function (input, init) {
    let url = null;
    try { url = typeof input === 'string' ? input : (input && input.url); } catch (e) {}
    if (url) {
      const r = rewrite(url);
      if (r) {
        if (typeof input === 'string') return NATIVE_FETCH(r, init);
        return NATIVE_FETCH(new Request(r, input), init);
      }
    }
    return NATIVE_FETCH(input, init);
  };
  const NativeXHR = window.XMLHttpRequest;
  window.XMLHttpRequest = function () {
    const xhr = new NativeXHR();
    const nativeOpen = xhr.open.bind(xhr);
    xhr.open = function (method, url, ...rest) {
      if (typeof url === 'string') { const r = rewrite(url); if (r) url = r; }
      return nativeOpen(method, url, ...rest);
    };
    return xhr;
  };
})();
</script>
"""


class StrudelError(RuntimeError):
    """Raised when the local Strudel server cannot start or serve."""


def _xdg_root() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        "~/.local/share"
    )
    return pathlib.Path(base) / "miau-dio" / "strudel"


def samples_dir() -> pathlib.Path:
    d = _xdg_root() / "samples"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> pathlib.Path:
    d = _xdg_root() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_path() -> pathlib.Path | None:
    """Optional request log destination, from MIAU_STRUDEL_LOG."""
    raw = os.environ.get("MIAU_STRUDEL_LOG")
    if not raw:
        return None
    p = pathlib.Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _log_request(status: int, method: str, path: str, target: str) -> None:
    lp = _log_path()
    if lp is None:
        return
    with lp.open("a", encoding="utf-8") as f:
        f.write(f"{status} {method} {path} -> {target}\n")


def _list_flat_samples() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(samples_dir().iterdir()):
        if p.is_file() and p.suffix.lower() in (".wav", ".mp3", ".ogg"):
            out[p.stem] = f"/samples/{p.name}"
    return out


def _render_index() -> bytes:
    src = _SITE / "index.html"
    if not src.is_file():
        raise StrudelError(f"index.html missing in vendored site: {src}")
    html = src.read_text(encoding="utf-8")
    # Inject the shim right after <head> so it runs before any other script.
    marker = "<head>"
    idx = html.find(marker)
    if idx < 0:
        raise StrudelError("vendored index.html has no <head> tag")
    inject_at = idx + len(marker)
    patched = html[:inject_at] + _FETCH_SHIM + html[inject_at:]
    return patched.encode("utf-8")


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status: int, ctype: str, body: bytes, target: str = "") -> None:
        _log_request(status, self.command or "?", self.path or "?", target)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: pathlib.Path) -> None:
        if not path.is_file():
            self._send(404, "text/plain", b"not found", str(path))
            return
        self._send(200, self._ctype_for(path), path.read_bytes(), str(path))

    @staticmethod
    def _ctype_for(path: pathlib.Path) -> str:
        ext = path.suffix.lower()
        return {
            ".js": "application/javascript",
            ".mjs": "application/javascript",
            ".json": "application/json",
            ".webmanifest": "application/manifest+json",
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".otf": "font/otf",
            ".xml": "application/xml",
            ".txt": "text/plain; charset=utf-8",
        }.get(ext, "application/octet-stream")

    def _safe_join(self, root: pathlib.Path, rel: str) -> pathlib.Path | None:
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            return None
        return root / rel

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            try:
                self._send(200, "text/html; charset=utf-8", _render_index())
            except StrudelError as e:
                self._send(500, "text/plain", str(e).encode())
            return

        if self.path == "/samples/index.json":
            self._send(200, "application/json",
                       json.dumps(_list_flat_samples()).encode())
            return

        if self.path.startswith("/samples/"):
            rel = self.path[len("/samples/"):]
            target = self._safe_join(samples_dir(), rel)
            if target is None:
                self._send(400, "text/plain", b"bad path")
                return
            self._serve_file(target)
            return

        if self.path.startswith("/shim/"):
            rel = self.path[len("/shim/"):]
            target = self._safe_join(cache_dir(), rel)
            if target is None:
                self._send(400, "text/plain", b"bad path")
                return
            self._serve_file(target)
            return

        # Fall through to the vendored site (/_astro/*, /fonts/*, etc.).
        rel = self.path.split("?", 1)[0].lstrip("/")
        if not rel:
            self._send(404, "text/plain", b"not found")
            return
        target = self._safe_join(_SITE, rel)
        if target is None:
            self._send(400, "text/plain", b"bad path")
            return
        self._serve_file(target)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(port: int = 0, host: str = "127.0.0.1") -> tuple[_Server, str]:
    if not (_SITE / "index.html").is_file():
        raise StrudelError(f"site missing: {_SITE / 'index.html'}")
    try:
        srv = _Server((host, port), _Handler)
    except OSError as e:
        raise StrudelError(f"cannot bind {host}:{port}: {e}") from e
    url = f"http://{host}:{srv.server_address[1]}/"
    return srv, url


def serve_background(port: int = 0, host: str = "127.0.0.1"
                     ) -> tuple[_Server, str, threading.Thread]:
    srv, url = serve(port=port, host=host)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, url, th


__all__ = [
    "StrudelError",
    "cache_dir",
    "samples_dir",
    "serve",
    "serve_background",
]
