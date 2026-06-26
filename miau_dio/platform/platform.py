"""Platform detection and standard paths for Debian and Termux."""
import os
import pathlib
import shutil


def is_termux() -> bool:
    """True when running inside Termux on Android."""
    return "com.termux" in os.environ.get("PREFIX", "")


def pkg_install_cmd() -> list[str]:
    """Return the package-install command prefix for the current platform."""
    if is_termux():
        return ["pkg", "install", "-y"]
    if shutil.which("apt"):
        return ["sudo", "apt", "install", "-y"]
    raise RuntimeError("unsupported platform: no pkg or apt found")


def _data_home() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = pathlib.Path(base) / "miau-dio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assets_dir() -> pathlib.Path:
    """Locate the bundled assets/ dir shipped inside the package."""
    # platform.py is at miau_dio/platform/platform.py; assets/ sits at repo root.
    here = pathlib.Path(__file__).resolve()
    return here.parent.parent.parent / "assets"


def bin_dir() -> pathlib.Path:
    """User-writable dir on PATH for built binaries (e.g. abc2midi)."""
    d = pathlib.Path(os.path.expanduser("~/.local/bin"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def soundfont_path() -> pathlib.Path:
    """Where the SoundFont lives once installed."""
    return _data_home() / "TimGM6mb.sf2"


def audio_player() -> list[str]:
    """Return a command prefix to play a wav file on this platform.

    The file path is appended by the caller. Picks the first available
    player; sox 'play' works on Termux, aplay/mpv are common on Debian.
    """
    candidates = (
        ["play", "-q"],      # sox, works on Termux and Debian
        ["aplay", "-q"],     # ALSA, common on Debian desktop
        ["mpv", "--no-video", "--really-quiet"],
    )
    for c in candidates:
        if shutil.which(c[0]):
            return c
    raise RuntimeError("no audio player found (install sox, alsa-utils or mpv)")
