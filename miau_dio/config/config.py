"""Persistent user defaults for idea creation.

Factory defaults are C major, 4/4, eighth-note unit. Users override them
with `config set`, stored as JSON in the data dir. Explicit command flags
still take precedence over these stored values.
"""
import json
import os
import pathlib

_FACTORY = {"key": "C", "meter": "4/4", "unit": "1/8", "bpm": "120"}


def _config_path() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = pathlib.Path(base) / "miau-dio"
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"


def load() -> dict[str, str]:
    """Return stored defaults merged over the factory defaults."""
    p = _config_path()
    stored = json.loads(p.read_text()) if p.exists() else {}
    return {**_FACTORY, **stored}


def get(field: str) -> str:
    return load()[field]


def set_value(field: str, value: str) -> None:
    """Persist one default. Unknown fields are rejected."""
    if field not in _FACTORY:
        raise KeyError(f"unknown config field: {field} (valid: {', '.join(_FACTORY)})")
    p = _config_path()
    stored = json.loads(p.read_text()) if p.exists() else {}
    stored[field] = value
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(stored, indent=2))
    tmp.replace(p)
