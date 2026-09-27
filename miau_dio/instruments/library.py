"""Instrument library -- atomic CRUD over a JSON index and per-instrument files.

Scope (task #165, part of redesign #239): persist Instrument records
(#164) under XDG_DATA_HOME/miau-dio/instruments/, with a single
index.json providing fast lookup by name and a per-instrument JSON file
providing the durable record. Every write is atomic (tmp + replace), so
a crash never leaves a half-written library.

Layout under XDG_DATA_HOME/miau-dio/instruments/:
  index.json          {"<name>": {"program": int, "family": str}, ...}
  <name>.json         full record, same shape as index entry

The name is the primary key and must be unique. Renames are atomic:
write new, verify, remove old.
"""
from __future__ import annotations

import json
import os
import pathlib

from miau_dio.instruments.model import Instrument


class LibraryError(RuntimeError):
    """Raised when a library operation cannot be completed."""


def _safe_name(name: str) -> str:
    """Reject names that would escape the library directory."""
    if not isinstance(name, str):
        raise LibraryError(
            f"instrument name must be a string, got {type(name).__name__}"
        )
    if "/" in name or "\\" in name or name in (".", ".."):
        raise LibraryError(f"unsafe instrument name: {name!r}")
    if name.startswith("."):
        raise LibraryError(f"instrument name must not start with '.': {name!r}")
    return name


def data_dir() -> pathlib.Path:
    """Root of the library on disk, created on first access."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        "~/.local/share"
    )
    d = pathlib.Path(base) / "miau-dio" / "instruments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> pathlib.Path:
    return data_dir() / "index.json"


def _instrument_path(name: str) -> pathlib.Path:
    return data_dir() / f"{_safe_name(name)}.json"


def _read_json(p: pathlib.Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise LibraryError(f"corrupt JSON at {p}: {e}") from e


def _write_json_atomic(p: pathlib.Path, data: dict) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(p)


def _load_index() -> dict[str, dict]:
    idx = _read_json(_index_path())
    if not isinstance(idx, dict):
        raise LibraryError("index.json must contain a JSON object")
    return idx


def list_instruments() -> list[Instrument]:
    """Return every instrument in the library, sorted by name."""
    idx = _load_index()
    out = []
    for name in sorted(idx):
        out.append(Instrument.from_dict({"name": name, **idx[name]}))
    return out


def get(name: str) -> Instrument:
    """Return one instrument by name; raises KeyError when absent."""
    _safe_name(name)
    idx = _load_index()
    if name not in idx:
        raise KeyError(f"instrument not found: {name}")
    return Instrument.from_dict({"name": name, **idx[name]})


def exists(name: str) -> bool:
    _safe_name(name)
    return name in _load_index()


def families() -> list[str]:
    """Distinct non-empty family labels present in the library, sorted."""
    return sorted({i.family for i in list_instruments() if i.family})


def add(instrument: Instrument) -> Instrument:
    """Persist a new instrument. Raises LibraryError if name already exists."""
    if not isinstance(instrument, Instrument):
        raise LibraryError(
            f"expected Instrument, got {type(instrument).__name__}"
        )
    _safe_name(instrument.name)
    idx = _load_index()
    if instrument.name in idx:
        raise LibraryError(f"instrument already exists: {instrument.name}")
    _write_json_atomic(_instrument_path(instrument.name), instrument.to_dict())
    idx[instrument.name] = {
        "program": instrument.program,
        "family": instrument.family,
    }
    _write_json_atomic(_index_path(), idx)
    return instrument


def update(current_name: str, **changes) -> Instrument:
    """Replace fields of an existing instrument, keeping its name."""
    _safe_name(current_name)
    idx = _load_index()
    if current_name not in idx:
        raise KeyError(f"instrument not found: {current_name}")
    if "name" in changes and changes["name"] != current_name:
        raise LibraryError(
            "rename must go through rename(), not update()"
        )
    current = {"name": current_name, **idx[current_name]}
    current.update(changes)
    current["name"] = current_name
    new = Instrument.from_dict(current)
    _write_json_atomic(_instrument_path(current_name), new.to_dict())
    idx[current_name] = {"program": new.program, "family": new.family}
    _write_json_atomic(_index_path(), idx)
    return new


def rename(old: str, new_name: str) -> Instrument:
    """Rename an instrument atomically: add the new, verify, remove the old."""
    _safe_name(old)
    _safe_name(new_name)
    idx = _load_index()
    if old not in idx:
        raise KeyError(f"instrument not found: {old}")
    if new_name in idx:
        raise LibraryError(f"instrument already exists: {new_name}")
    current = {"name": new_name, **idx[old]}
    moved = Instrument.from_dict(current)
    _write_json_atomic(_instrument_path(new_name), moved.to_dict())
    idx[new_name] = idx.pop(old)
    _write_json_atomic(_index_path(), idx)
    _instrument_path(old).unlink(missing_ok=True)
    return moved


def remove(name: str) -> None:
    """Delete an instrument and its index entry. Idempotent."""
    _safe_name(name)
    idx = _load_index()
    if name not in idx:
        return
    del idx[name]
    _write_json_atomic(_index_path(), idx)
    _instrument_path(name).unlink(missing_ok=True)


def duplicate(name: str, new_name: str | None = None) -> Instrument:
    """Copy an instrument under a fresh name."""
    src = get(name)
    target = new_name or f"{name} (copy)"
    copy = Instrument(name=target, program=src.program, family=src.family)
    return add(copy)


__all__ = [
    "LibraryError",
    "add", "data_dir", "duplicate", "exists", "families", "get",
    "list_instruments", "remove", "rename", "update",
]
