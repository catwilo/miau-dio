"""Sample pack catalog -- metadata only, no audio files.

Scope (task #174, part of redesign #168): the catalog is a small list of
known sample packs whose manifests point at remote URLs. Only this
metadata lives in git; every actual audio file is downloaded on demand
by `miau-dio sample install <pack>` into
XDG_DATA_HOME/miau-dio/strudel/cache/, where the live server's fetch
shim resolves it offline.

Each entry has:
  name          key used on the command line
  description   short human description
  license       what the pack is licensed under
  manifest_url  the strudel.json (or equivalent) describing the pack
  approx_mb     approximate download size, for the user's decision
  tags          searchable keywords

Adding a pack: append an entry, no other code change required.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    name: str
    description: str
    license: str
    manifest_url: str
    approx_mb: float
    tags: tuple[str, ...]


CATALOG: dict[str, Pack] = {
    "uzu": Pack(
        name="uzu",
        description=(
            "Compact drum kit by tidalcycles. Kicks, snares, hats, "
            "claps, breaks. Good default for techno / breakbeat."
        ),
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/tidalcycles/"
            "uzu-drumkit/main/strudel.json"
        ),
        approx_mb=2.3,
        tags=("drums", "techno", "breakbeat"),
    ),
    "piano": Pack(
        name="piano",
        description="Salamander Grand Piano, 29 chromatic notes, MP3.",
        license="CC-BY-3.0 (Salamander Grand Piano)",
        manifest_url=(
            "https://raw.githubusercontent.com/felixroos/"
            "dough-samples/main/piano.json"
        ),
        approx_mb=8.7,
        tags=("keys", "piano"),
    ),
    "dirt": Pack(
        name="dirt",
        description=(
            "Dirt-Samples collection by tidalcycles: broad set of "
            "percussive and textural sounds."
        ),
        license="CC0-1.0 / various per sample",
        manifest_url=(
            "https://raw.githubusercontent.com/felixroos/"
            "dough-samples/main/Dirt-Samples.json"
        ),
        approx_mb=1.4,
        tags=("percussion", "textures"),
    ),
    "mridangam": Pack(
        name="mridangam",
        description="Mridangam (South Indian drum) sample set.",
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/felixroos/"
            "dough-samples/main/mridangam.json"
        ),
        approx_mb=0.2,
        tags=("drums", "world"),
    ),
}


def get(name: str) -> Pack:
    if name not in CATALOG:
        raise KeyError(f"unknown pack: {name!r}")
    return CATALOG[name]


def all_packs() -> list[Pack]:
    return sorted(CATALOG.values(), key=lambda p: p.name)


__all__ = ["CATALOG", "Pack", "all_packs", "get"]
