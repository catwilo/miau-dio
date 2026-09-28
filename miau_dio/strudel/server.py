"""Local Strudel server -- vendored official site + fetch shim + samples.

Scope (task #174, part of redesign #168): `miau-dio live` runs a stdlib
HTTP server on localhost that serves the **official Strudel site**
vendored into `site/` (HTML + Astro chunks + fonts + CSS), plus:

  GET /shim/<host>/<path>      -> XDG cache (samples, hydra, jzz, ...)
  GET /samples/<file>          -> user wavs under XDG
  GET /samples/index.json      -> {name: /samples/<file>}
  GET /miau/<file>             -> our injected JS/CSS assets
  GET /project/info            -> {name, patterns} of the bound project
  GET /project/pattern/<name>  -> raw pattern content
  POST /project/pattern/<name> -> write pattern under <dir>/patterns/
  anything else                -> site/<path> (static)

The served index.html is the official one with a small fetch/XHR shim
injected before any <script>. Requests to known remote hosts
(raw.githubusercontent.com, cdn.jsdelivr.net, unpkg.com,
felixroos.github.io, shabda.ndre.gr) are rewritten to /shim/<host>/<path>
which the server resolves from XDG_DATA_HOME/miau-dio/strudel/cache/.
Uncached files 404, so the browser never reaches the network.

When a project directory is bound (via `--at <dir>`), the injected
project bridge lets the browser read/write files in its `patterns/`
folder. Without --at, /project/info returns 404 and the bridge stays
inert; the offline REPL works exactly as before.

The injected assets live as plain files in `inject/` (fetch_shim.js,
miau_bar.js) so no JavaScript is embedded in Python strings -- keeping
syntax errors out of the source. `miau_bar.js` is the single unified
toolbar: animations toggle plus project save/load when `--at` is bound.
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
_INJECT = _HERE / "inject"
_PROJECT_DIR = None

# Hosts the browser must never reach. Any URL pointing at one of these is
# rewritten to /shim/<host>/<path> by inject/fetch_shim.js and resolved
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
# body before replying 413. Draining keeps the client from seeing a broken
# pipe (http.server does not consume an unread body on its own). Beyond
# this limit the server stops reading and closes the connection, accepting
# that the client will see a reset -- no local caller should ever approach
# this ceiling.
HARD_DRAIN_LIMIT = 100 * 1024 * 1024


class StrudelError(RuntimeError):
    """Raised when the local Strudel server cannot start or serve."""


# ---- project binding -------------------------------------------------------

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
    """Snapshot of the bound project: name and pattern files."""
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
    return {"name": name, "patterns": files}


def _safe_pattern_name(raw):
    """Return a safe pattern filename or None.

    Rejects path separators, `..`, leading dots and empty names. Appends
    `.js` when missing so callers can send either form.
    """
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    if (not name or "/" in name or "\\" in name
            or name in (".", "..") or name.startswith(".")):
        return None
    if not name.endswith(".js"):
        name = name + ".js"
    return name


# ---- XDG paths -------------------------------------------------------------

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


def _list_flat_samples() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(samples_dir().iterdir()):
        if p.is_file() and p.suffix.lower() in (".wav", ".mp3", ".ogg"):
            out[p.stem] = f"/samples/{p.name}"
    return out


# ---- index rendering -------------------------------------------------------

def _shim_hosts_js():
    return "[" + ", ".join(json.dumps(h) for h in SHIM_HOSTS) + "]"


def _render_index() -> bytes:
    """Serve site/index.html with our injected assets appended to <head>.

    The assets live as files under inject/ and are referenced by URL; no
    JavaScript is embedded in this Python module.
    """
    src = _SITE / "index.html"
    if not src.is_file():
        raise StrudelError(f"index.html missing in vendored site: {src}")
    html = src.read_text(encoding="utf-8")
    marker = "<head>"
    idx = html.find(marker)
    if idx < 0:
        raise StrudelError("vendored index.html has no <head> tag")
    inject_at = idx + len(marker)

    # The fetch shim must run before any other script; serve it as an
    # external asset so the browser loads it synchronously.
    # /miau/fetch_shim.js returns the file with __SHIM_HOSTS__ replaced
    # with the actual list from SHIM_HOSTS (single source of truth).
    head = (
        '<script src="/miau/fetch_shim.js"></script>'
        '<script defer src="/miau/miau_bar.js"></script>'
    )
    patched = html[:inject_at] + head + html[inject_at:]
    return patched.encode("utf-8")


# ---- handler ---------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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

    @staticmethod
    def _safe_join(root: pathlib.Path, rel: str):
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            return None
        return root / rel

    def _serve_file(self, path: pathlib.Path) -> None:
        if not path.is_file():
            self._send(404, "text/plain", b"not found")
            return
        self._send(200, self._ctype_for(path), path.read_bytes())

    def _serve_inject(self, name: str) -> None:
        """Serve an inject/ asset, substituting __SHIM_HOSTS__ in JS files."""
        path = self._safe_join(_INJECT, name)
        if path is None or not path.is_file():
            self._send(404, "text/plain", b"not found")
            return
        body = path.read_bytes()
        if name == "fetch_shim.js":
            body = body.replace(b"__SHIM_HOSTS__",
                                _shim_hosts_js().encode())
        self._send(200, self._ctype_for(path), body)

    def _drain_body(self, length: int) -> None:
        remaining = length
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            try:
                self._send(200, "text/html; charset=utf-8", _render_index())
            except StrudelError as e:
                self._send(500, "text/plain", str(e).encode())
            return

        if self.path.startswith("/miau/"):
            self._serve_inject(self.path[len("/miau/"):].split("?", 1)[0])
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
            raw = urllib.parse.unquote(self.path[len("/project/pattern/"):])
            name = _safe_pattern_name(raw)
            if name is None:
                self._send(400, "text/plain", b"bad pattern name")
                return
            self._serve_file(_PROJECT_DIR / "patterns" / name)
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

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/project/pattern/"):
            self._send(404, "text/plain", b"not found")
            return
        if _PROJECT_DIR is None:
            self._send(404, "text/plain", b"no project bound")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0:
            self._send(400, "text/plain", b"bad content-length")
            return
        if length > MAX_PATTERN_BYTES:
            if length <= HARD_DRAIN_LIMIT:
                self._drain_body(length)
            self._send(413, "text/plain", b"payload too large")
            return
        raw = urllib.parse.unquote(self.path[len("/project/pattern/"):])
        name = _safe_pattern_name(raw)
        if name is None:
            self._send(400, "text/plain", b"bad pattern name")
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
    "MAX_PATTERN_BYTES",
    "SHIM_HOSTS",
    "StrudelError",
    "cache_dir",
    "samples_dir",
    "serve",
    "serve_background",
]
