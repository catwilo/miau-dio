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


def preview(name: str, count: int = 3) -> list[pathlib.Path]:
    """Download up to `count` sample assets to temp files and return them.

    Picks the first asset of each distinct top-level key in the manifest
    so the preview covers different sounds (kick, snare, ...). Does NOT
    touch the XDG cache: writes to a TemporaryDirectory that the caller
    owns. Files are small (individual samples, not the full pack).

    If the pack is already installed, reads from the cache instead of
    fetching over the network.
    """
    import tempfile
    pack = catalog.get(name)

    # If installed, use the cached copy of the manifest and assets.
    if is_installed(name):
        record = json.loads(_record_path(name).read_text())
        cached_manifest_url = record.get("manifest_url")
        cached_files = record.get("files", [])
        if cached_manifest_url and cached_files:
            # Pick the first file of each top-level category dir under the
            # manifest URL's path.
            base_prefix = None
            # Derive the base prefix from the manifest URL's path.
            mu = urllib.parse.urlparse(cached_manifest_url)
            base_dir = mu.path.rsplit("/", 1)[0].lstrip("/")
            # Find first file per parent directory of the manifest.
            seen_dirs = set()
            picks = []
            for rel in cached_files:
                rel_str = str(rel)
                # cached_files are relative to cache_dir, e.g.
                # raw.githubusercontent.com/tidalcycles/uzu-drumkit/main/bd/x.wav
                # Strip host.
                parts = rel_str.split("/", 1)
                if len(parts) < 2:
                    continue
                path_in_repo = parts[1]
                if not path_in_repo.startswith(base_dir + "/"):
                    continue
                sub = path_in_repo[len(base_dir) + 1:]
                category = sub.split("/", 1)[0] if "/" in sub else ""
                if not category or category in seen_dirs:
                    continue
                seen_dirs.add(category)
                picks.append(cache_dir() / rel_str)
                if len(picks) >= count:
                    break
            if picks:
                return picks

    # Not installed (or install incomplete): fetch on demand.
    body, urls = _collect_urls(pack)
    manifest = json.loads(body)
    base = manifest.get("_base", pack.manifest_url.rsplit("/", 1)[0] + "/")
    seen_dirs = set()
    picks = []
    for u in urls:
        if u == pack.manifest_url:
            continue
        # Category = first path component below base.
        if not u.startswith(base):
            continue
        sub = u[len(base):]
        category = sub.split("/", 1)[0] if "/" in sub else ""
        if not category or category in seen_dirs:
            continue
        seen_dirs.add(category)
        picks.append(u)
        if len(picks) >= count:
            break
    if not picks:
        raise SampleError(f"no sample assets found in {name}")

    td = pathlib.Path(tempfile.mkdtemp(prefix=f"miau-preview-{name}-"))
    out = []
    for u in picks:
        fname = u.rsplit("/", 1)[-1] or "sample.wav"
        dest = td / fname
        dest.write_bytes(_fetch(u))
        out.append(dest)
    return out


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
    "is_installed", "preview", "remove", "size_on_disk",
]
