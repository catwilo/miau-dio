"""Sample pack installer -- downloads packs into the XDG cache.

Scope (task #174, part of redesign #168): `miau-dio sample install`
mirrors a pack's manifest and all its audio files into
XDG_DATA_HOME/miau-dio/strudel/cache/<host>/<path>, which the live
server's fetch shim resolves offline. Nothing is ever fetched by the
browser: the shim 404s on any uncached URL. The user controls exactly
what gets cached by running the CLI commands.

Layout on disk:
  cache/<host>/<path>            every asset the pack references
  cache/.packs/<name>.json       record of what was installed
"""
from __future__ import annotations

import json
import pathlib
import shutil
import urllib.parse
import urllib.request

from miau_dio.strudel import catalog


class SampleError(RuntimeError):
    """Raised when a sample install/remove cannot be completed."""


def _xdg_root() -> pathlib.Path:
    import os
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        "~/.local/share"
    )
    return pathlib.Path(base) / "miau-dio" / "strudel"


def cache_dir() -> pathlib.Path:
    d = _xdg_root() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _packs_dir() -> pathlib.Path:
    d = cache_dir() / ".packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _record_path(name: str) -> pathlib.Path:
    return _packs_dir() / f"{name}.json"


def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "miau-dio-sample/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        raise SampleError(f"fetch failed for {url}: {e}") from e


def _url_to_cache_rel(url: str) -> pathlib.Path:
    """Map an http(s) URL to <host>/<path> (relative to cache_dir)."""
    u = urllib.parse.urlparse(url)
    if not u.netloc:
        raise SampleError(f"unsupported URL (no host): {url}")
    return pathlib.Path(u.netloc) / u.path.lstrip("/")


def _walk_manifest(base: str, value) -> list[str]:
    """Return every asset URL referenced by a manifest subtree."""
    urls: list[str] = []
    if isinstance(value, str):
        urls.append(urllib.parse.urljoin(base, value))
    elif isinstance(value, list):
        for v in value:
            urls.extend(_walk_manifest(base, v))
    elif isinstance(value, dict):
        b = value.get("_base", base)
        for k, v in value.items():
            if k == "_base":
                continue
            urls.extend(_walk_manifest(b, v))
    return urls


def _collect_urls(pack: catalog.Pack) -> tuple[str, list[str]]:
    """Return (manifest_body_decoded, all_asset_urls_including_manifest)."""
    body = _fetch(pack.manifest_url).decode("utf-8")
    try:
        manifest = json.loads(body)
    except json.JSONDecodeError as e:
        raise SampleError(f"bad manifest JSON for {pack.name}: {e}") from e
    base = manifest.get("_base", pack.manifest_url.rsplit("/", 1)[0] + "/")
    assets = _walk_manifest(base, {k: v for k, v in manifest.items()
                                   if k != "_base"})
    # Deduplicate while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for u in [pack.manifest_url] + assets:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return body, uniq


def is_installed(name: str) -> bool:
    return _record_path(name).is_file()


def installed() -> list[str]:
    return sorted(p.stem for p in _packs_dir().glob("*.json"))


def install(name: str, on_progress=None) -> list[pathlib.Path]:
    """Download a pack into the cache; return the list of local paths."""
    pack = catalog.get(name)
    if is_installed(name):
        raise SampleError(f"pack already installed: {name}")
    _, urls = _collect_urls(pack)
    written: list[pathlib.Path] = []
    try:
        for url in urls:
            rel = _url_to_cache_rel(url)
            dest = cache_dir() / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if on_progress:
                on_progress(url)
            body = _fetch(url)
            dest.write_bytes(body)
            written.append(rel)
    except SampleError:
        for rel in written:
            (cache_dir() / rel).unlink(missing_ok=True)
        raise
    record = {"name": name, "manifest_url": pack.manifest_url,
              "files": [str(r) for r in written]}
    _record_path(name).write_text(json.dumps(record, indent=2))
    return [cache_dir() / r for r in written]


def remove(name: str) -> int:
    """Delete a pack's files. Returns the number of files removed."""
    if not is_installed(name):
        raise SampleError(f"pack not installed: {name}")
    record = json.loads(_record_path(name).read_text())
    removed = 0
    for rel in record.get("files", []):
        p = cache_dir() / rel
        if p.is_file():
            p.unlink()
            removed += 1
    _record_path(name).unlink(missing_ok=True)
    # Prune now-empty dirs under the cache root (but not the root itself).
    for d in sorted(cache_dir().rglob("*"), reverse=True):
        if d.is_dir() and not d.name.startswith("."):
            try:
                next(d.iterdir())
            except StopIteration:
                shutil.rmtree(d, ignore_errors=True)
    return removed


def size_on_disk(name: str) -> int:
    """Total bytes currently used by an installed pack."""
    if not is_installed(name):
        return 0
    record = json.loads(_record_path(name).read_text())
    total = 0
    for rel in record.get("files", []):
        p = cache_dir() / rel
        if p.is_file():
            total += p.stat().st_size
    return total


__all__ = [
    "SampleError", "cache_dir", "install", "installed",
    "is_installed", "remove", "size_on_disk",
]
