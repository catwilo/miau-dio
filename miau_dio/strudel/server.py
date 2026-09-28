"""Local Strudel server -- vendored official site + fetch shim + samples.

Scope (task #174, part of redesign #168): `miau-dio live` runs a stdlib
HTTP server on localhost that serves the **official Strudel site**
vendored into `site/` (HTML + Astro chunks + fonts + CSS), plus:

  GET /shim/<host>/<path>      -> XDG cache (samples, hydra, jzz, ...)
  GET /samples/<file>          -> user wavs under XDG
  GET /samples/index.json      -> {name: /samples/<file>}
  anything else                -> site/<path> (static)

When a project directory is bound (via `miau-dio live --at <dir>`),
three extra endpoints let the browser read/write files inside the
project's `patterns/` folder:

  GET  /project/info              -> {"name", "patterns": [...], "current"}
  GET  /project/pattern/<name>    -> raw file content
  POST /project/pattern/<name>    -> write body to <dir>/patterns/<name>

Without --at these endpoints return 404 and the injected UI shows no
project buttons; the plain offline REPL works exactly as before.

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
import urllib.parse

_HERE = pathlib.Path(__file__).resolve().parent
_SITE = _HERE / "site"
_PROJECT_DIR = None

# Hosts the browser must never reach. Any URL pointing at one of these is
# rewritten to /shim/<host>/<path> by the injected fetch shim and resolved
# from XDG_DATA_HOME. Kept as a Python constant so tests can assert against
# it (see test_strudel_server.TestOfflineInvariant).
SHIM_HOSTS = (
    "raw.githubusercontent.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "felixroos.github.io",
    "shabda.ndre.gr",
)

# Hard cap on pattern files. Keeps the local server safe against a runaway
# client sending an unbounded body; patterns are a few KB at most.
MAX_PATTERN_BYTES = 1024 * 1024

# When a request exceeds MAX_PATTERN_BYTES, the server drains the pending
# body before replying 413. Draining keeps the client from seeing a
# broken pipe (http.server does not consume an unread body on its own).
# Beyond this limit the server stops reading and closes the connection,
# accepting that the client will see a reset -- no local caller should
# ever approach this ceiling.
HARD_DRAIN_LIMIT = 100 * 1024 * 1024


def _shim_hosts_js():
    return "[" + ", ".join(repr(h) for h in SHIM_HOSTS) + "]"


def _set_project_dir(path):
    """Bind (or clear) the current project for /project/* endpoints."""
    global _PROJECT_DIR
    if path is None:
        _PROJECT_DIR = None
        return
    p = pathlib.Path(path).expanduser().resolve()
    if not (p / "project.json").is_file():
        raise StrudelError(
            f"--at requires a project directory (no project.json in {p})"
        )
    (p / "patterns").mkdir(parents=True, exist_ok=True)
    _PROJECT_DIR = p


def _project_info():
    """Snapshot of the bound project: name, pattern files, current."""
    if _PROJECT_DIR is None:
        return None
    try:
        data = json.loads((_PROJECT_DIR / "project.json").read_text())
        name = data.get("name", _PROJECT_DIR.name)
    except Exception:
        name = _PROJECT_DIR.name
    patterns_dir = _PROJECT_DIR / "patterns"
    files = sorted(p.name for p in patterns_dir.iterdir()
                   if p.is_file() and not p.name.startswith("."))
    return {"name": name, "patterns": files, "current": ""}

_FETCH_SHIM = """<script>
(function () {
  const NATIVE_FETCH = window.fetch.bind(window);
  const SHIM_HOSTS = __SHIM_HOSTS__;
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
<script>
// Project bridge -- only active when the server was started with --at.
// Uses window.strudelMirror to read/write the editor content.
(function () {
  async function info() {
    try {
      const r = await fetch('/project/info');
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }
  function setStatus(text) {
    const el = document.getElementById('miau-project-status');
    if (el) el.textContent = text;
  }
  async function refresh() {
    const i = await info();
    if (!i) return;
    setStatus(i.name + ' \u00b7 ' + i.patterns.length + ' pattern(s)');
  }
  async function savePattern() {
    if (!window.strudelMirror) { alert('editor not ready'); return; }
    const suggested = 'pattern-' + new Date().toISOString().slice(0, 10);
    const name = prompt('save pattern as:', suggested);
    if (!name) return;
    const body = window.strudelMirror.code || '';
    const r = await fetch('/project/pattern/' + encodeURIComponent(name),
                          { method: 'POST', body: body });
    if (!r.ok) { alert('save failed: ' + r.status); return; }
    setStatus('saved ' + name);
    refresh();
  }
  async function loadPattern() {
    const i = await info();
    if (!i || i.patterns.length === 0) { alert('no patterns saved yet'); return; }
    const name = prompt('load pattern:\n' + i.patterns.join('\n'));
    if (!name) return;
    const r = await fetch('/project/pattern/' + encodeURIComponent(name));
    if (!r.ok) { alert('load failed: ' + r.status); return; }
    const body = await r.text();
    if (!window.strudelMirror) { alert('editor not ready'); return; }
    window.strudelMirror.setCode(body);
    setStatus('loaded ' + name);
  }
  function install() {
    if (document.getElementById('miau-project-bar')) return;
    const bar = document.createElement('div');
    bar.id = 'miau-project-bar';
    bar.style.cssText = 'position:fixed;top:0;right:0;z-index:99999;' +
      'background:#18181b;color:#e6e6ea;padding:6px 10px;' +
      'font:12px/1.4 ui-monospace,Menlo,monospace;border:1px solid #2a2a2f;' +
      'border-top:0;border-right:0;border-radius:0 0 0 4px;' +
      'display:flex;gap:8px;align-items:center';
    const status = document.createElement('span');
    status.id = 'miau-project-status';
    status.style.cssText = 'color:#8a8a93';
    status.textContent = 'project';
    const btnSave = document.createElement('button');
    btnSave.textContent = 'save pattern';
    btnSave.style.cssText = 'background:#1f6f3f;color:#fff;border:0;' +
      'padding:3px 8px;border-radius:3px;font:inherit;cursor:pointer';
    btnSave.onclick = savePattern;
    const btnLoad = document.createElement('button');
    btnLoad.textContent = 'load pattern';
    btnLoad.style.cssText = 'background:#2a2a2f;color:#e6e6ea;border:0;' +
      'padding:3px 8px;border-radius:3px;font:inherit;cursor:pointer';
    btnLoad.onclick = loadPattern;
    bar.appendChild(btnSave);
    bar.appendChild(btnLoad);
    bar.appendChild(status);
    document.body.appendChild(bar);
    refresh();
  }
  window.addEventListener('DOMContentLoaded', async () => {
    const i = await info();
    if (i) install();
  });
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


_ANIM_TOGGLE_SCRIPT = """<script>
// Animations toggle -- always present. Toggles the two visual pulses the
// editor adds while a pattern plays (line highlight and flash). Audio is
// unaffected. Preference is persisted per browser in localStorage; the
// button is idempotent (second install is a no-op).
(function () {
  const KEY = 'miau-dio.animations';
  function readPref() {
    try { return localStorage.getItem(KEY) !== 'off'; }
    catch (e) { return true; }
  }
  function writePref(on) {
    try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch (e) {}
  }
  function apply(ed, on) {
    try {
      ed.updateSettings({
        isPatternHighlightingEnabled: on,
        isFlashEnabled: on,
      });
    } catch (e) { /* editor may not yet expose updateSettings */ }
  }
  function whenEditor(cb, tries) {
    tries = tries || 0;
    const ed = window.strudelMirror;
    if (ed && typeof ed.updateSettings === 'function') { cb(ed); return; }
    if (tries > 60) return;
    setTimeout(() => whenEditor(cb, tries + 1), 100);
  }
  function install() {
    if (document.getElementById('miau-anim-toggle')) return;
    const bar = document.createElement('div');
    bar.id = 'miau-anim-toggle';
    bar.style.cssText = 'position:fixed;bottom:0;right:0;z-index:99999;' +
      'background:#18181b;color:#e6e6ea;padding:5px 9px;' +
      'font:12px/1.4 ui-monospace,Menlo,monospace;' +
      'border:1px solid #2a2a2f;border-bottom:0;border-right:0;' +
      'border-radius:4px 0 0 0;display:flex;gap:6px;align-items:center';
    const btn = document.createElement('button');
    btn.type = 'button';
    let on = readPref();
    function render() {
      btn.textContent = 'animations: ' + (on ? 'on' : 'off');
      btn.style.cssText = 'background:' + (on ? '#1f6f3f' : '#2a2a2f') +
        ';color:#e6e6ea;border:0;padding:3px 8px;border-radius:3px;' +
        'font:inherit;cursor:pointer';
    }
    render();
    btn.addEventListener('click', () => {
      on = !on;
      writePref(on);
      render();
      whenEditor((ed) => apply(ed, on));
    });
    bar.appendChild(btn);
    document.body.appendChild(bar);
    whenEditor((ed) => apply(ed, on));
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
</script>
"""


def _render_index() -> bytes:
    src = _SITE / "index.html"
    if not src.is_file():
        raise StrudelError(f"index.html missing in vendored site: {src}")
    html = src.read_text(encoding="utf-8")
    marker = "<head>"
    idx = html.find(marker)
    if idx < 0:
        raise StrudelError("vendored index.html has no <head> tag")
    inject_at = idx + len(marker)
    shim = _FETCH_SHIM.replace("__SHIM_HOSTS__", _shim_hosts_js())
    patched = html[:inject_at] + shim + _ANIM_TOGGLE_SCRIPT + html[inject_at:]
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

    def _drain_body(self, length: int) -> None:
        """Consume `length` bytes from the request body without storing them.

        http.server does not drain an unread body, so a client that sent a
        large payload would see a broken pipe before reading our reply.
        Draining lets the 413 response land cleanly.
        """
        remaining = length
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

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

        if self.path == "/project/info":
            info = _project_info()
            if info is None:
                self._send(404, "text/plain", b"no project bound")
                return
            self._send(200, "application/json", json.dumps(info).encode())
            return

        if self.path.startswith("/project/pattern/"):
            if _PROJECT_DIR is None:
                self._send(404, "text/plain", b"no project bound")
                return
            name = urllib.parse.unquote(self.path[len("/project/pattern/"):])
            if (not name or "/" in name or "\\" in name
                    or name in (".", "..") or name.startswith(".")):
                self._send(400, "text/plain", b"bad pattern name")
                return
            if not name.endswith(".js"):
                name = name + ".js"
            self._serve_file(_PROJECT_DIR / "patterns" / name)
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

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/project/pattern/"):
            self._send(404, "text/plain", b"not found")
            return
        if _PROJECT_DIR is None:
            self._send(404, "text/plain", b"no project bound")
            return
        name = urllib.parse.unquote(self.path[len("/project/pattern/"):])
        if (not name or "/" in name or "\\" in name
                or name in (".", "..") or name.startswith(".")):
            self._send(400, "text/plain", b"bad pattern name")
            return
        if not name.endswith(".js"):
            name = name + ".js"
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0:
            self._send(400, "text/plain", b"bad content-length")
            return
        if length > MAX_PATTERN_BYTES:
            if length <= HARD_DRAIN_LIMIT:
                self._drain_body(length)
            self._send(413, "text/plain", b"payload too large")
            return
        body = self.rfile.read(length) if length else b""
        target = _PROJECT_DIR / "patterns" / name
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(target)
        self._send(200, "application/json",
                   json.dumps({"saved": name, "bytes": len(body)}).encode())


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(port: int = 0, host: str = "127.0.0.1", project_dir=None):
    if not (_SITE / "index.html").is_file():
        raise StrudelError(f"site missing: {_SITE / 'index.html'}")
    _set_project_dir(project_dir)
    try:
        srv = _Server((host, port), _Handler)
    except OSError as e:
        raise StrudelError(f"cannot bind {host}:{port}: {e}") from e
    url = f"http://{host}:{srv.server_address[1]}/"
    return srv, url


def serve_background(port: int = 0, host: str = "127.0.0.1",
                     project_dir=None):
    srv, url = serve(port=port, host=host, project_dir=project_dir)
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
