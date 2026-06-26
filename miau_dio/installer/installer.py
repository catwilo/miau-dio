"""Installer: set up all dependencies from local assets, no network.

Strategy per backend:
  - abcmidi: compile abc2midi from the bundled source subset in assets/.
  - timidity / sox: install from the platform package manager.
The bundled SoundFont is copied into the data dir for timidity to use.
"""
import os
import shutil
import subprocess

import typer

from miau_dio.backends.backend import BACKENDS, Backend, is_installed
from miau_dio.platform.platform import (
    assets_dir, bin_dir, is_termux, pkg_install_cmd, soundfont_path,
)

# Compile flags discovered to build abc2midi cleanly with clang/gcc.
_ABC2MIDI_SOURCES = [
    "parseabc.c", "store.c", "genmidi.c", "midifile.c",
    "queues.c", "parser2.c", "stresspat.c", "music_utils.c",
]
_ABC2MIDI_FLAGS = ["-DANSILIBS", "-DHAVE_CONFIG_H", "-O2", "-I."]


def _cc() -> str:
    """Pick an available C compiler."""
    for cc in ("clang", "gcc", "cc"):
        if shutil.which(cc):
            return cc
    raise RuntimeError("no C compiler found (need clang or gcc)")


def build_abc2midi() -> None:
    """Compile abc2midi from the bundled source into bin_dir()."""
    src = assets_dir() / "abc2midi-src"
    out = bin_dir() / "abc2midi"
    cmd = [_cc(), *_ABC2MIDI_FLAGS, "-o", str(out), *_ABC2MIDI_SOURCES, "-lm"]
    subprocess.run(cmd, cwd=str(src), check=True)
    out.chmod(0o755)


def install_soundfont() -> None:
    """Copy the bundled SoundFont into the data dir."""
    src = assets_dir() / "TimGM6mb.sf2"
    dest = soundfont_path()
    if not dest.exists():
        shutil.copy2(src, dest)


def install_pkg(pkg: str) -> None:
    subprocess.run([*pkg_install_cmd(), pkg], check=True)


def _platform_pkg(b: Backend) -> str | None:
    return b.termux_pkg if is_termux() else b.apt_pkg


def install(name: str) -> None:
    """Install one backend by name using the right local strategy."""
    b = BACKENDS[name]
    if name == "abcmidi":
        build_abc2midi()
    else:
        pkg = _platform_pkg(b)
        if pkg is None:
            raise RuntimeError(f"no package for {b.name} on this platform")
        install_pkg(pkg)


def ensure(names: list[str], auto: bool = False) -> None:
    """Ensure each backend is present; install missing ones from assets."""
    for name in names:
        b = BACKENDS[name]
        if is_installed(b):
            continue
        if auto or typer.confirm(f"{b.name} is missing. Install?"):
            install(name)
        else:
            raise typer.Abort()
    # timidity always needs the SoundFont present to produce audio.
    if "timidity" in names:
        install_soundfont()
