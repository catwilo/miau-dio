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
            "https://raw.githubusercontent.com/tidalcycles/"
            "Dirt-Samples/master/Dirt-Samples.json"
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
    "guitar": Pack(
        name="guitar",
        description=(
            "Acoustic guitar multisample from Iowa, via "
            "nbrosowsky/tonejs-instruments."
        ),
        license="CC-BY-3.0",
        manifest_url=(
            "https://raw.githubusercontent.com/nbrosowsky/"
            "tonejs-instruments/master/samples/guitar-acoustic/guitar.json"
        ),
        approx_mb=24.3,
        tags=("strings", "guitar", "acoustic"),
    ),
    "trumpet": Pack(
        name="trumpet",
        description=(
            "Trumpet, sustained, multi-velocity, multi-round-robin. "
            "VSCO 2 Community Edition."
        ),
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/"
            "master/Brass/Trumpet/sus/"
        ),
        approx_mb=38.7,
        tags=("brass", "trumpet", "wind"),
    ),
    "trumpet_stac": Pack(
        name="trumpet_stac",
        description=(
            "Trumpet, staccato, multi-velocity, multi-round-robin. "
            "VSCO 2 Community Edition."
        ),
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/"
            "master/Brass/Trumpet/stac/"
        ),
        approx_mb=14.0,
        tags=("brass", "trumpet", "staccato"),
    ),
    "trombone": Pack(
        name="trombone",
        description=(
            "Tenor trombone, sustained, multi-velocity. "
            "VSCO 2 Community Edition."
        ),
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/"
            "master/Brass/Tenor%20Trombone/sus/"
        ),
        approx_mb=57.4,
        tags=("brass", "trombone", "wind"),
    ),
    "trombone_stac": Pack(
        name="trombone_stac",
        description=(
            "Tenor trombone, staccato, multi-velocity, multi-round-robin. "
            "VSCO 2 Community Edition."
        ),
        license="CC0-1.0",
        manifest_url=(
            "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/"
            "master/Brass/Tenor%20Trombone/stac/"
        ),
        approx_mb=12.8,
        tags=("brass", "trombone", "staccato"),
    ),
}


def get(name: str) -> Pack:
    if name not in CATALOG:
        raise KeyError(f"unknown pack: {name!r}")
    return CATALOG[name]


def all_packs() -> list[Pack]:
    return sorted(CATALOG.values(), key=lambda p: p.name)


# Groups for `miau-dio live --samples <group>`. Only vendored packs
# (shipped in miau_dio/strudel/vendor/) are valid here; opt-in packs
# (piano, mridangam) live in the XDG cache and are never auto-loaded.
GROUPS: dict[str, tuple[str, ...]] = {
    "drums":   ("uzu", "dirt"),
    "brass":   ("trumpet", "trumpet_stac", "trombone", "trombone_stac"),
    "strings": ("guitar",),
    "all":     ("uzu", "dirt", "guitar", "trumpet", "trumpet_stac",
                "trombone", "trombone_stac"),
}


def resolve_samples(spec: str) -> list[str]:
    """Expand --samples value to a list of pack names.

    Accepts 'none' / '' (empty), a group name ('drums', 'brass', 'strings',
    'all'), or a comma-separated list of pack names. Raises KeyError for
    unknown names so cli.py can exit with a clear message.
    """
    if not spec or spec == "none":
        return []
    if spec in GROUPS:
        return list(GROUPS[spec])
    names = [s.strip() for s in spec.split(",") if s.strip()]
    for name in names:
        if name not in CATALOG:
            raise KeyError(f"unknown sample pack: {name!r}")
    return names


__all__ = ["CATALOG", "GROUPS", "Pack", "all_packs", "get",
           "resolve_samples"]
