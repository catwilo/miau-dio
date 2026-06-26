"""Backend registry: one entry per external binary.

Each backend declares how to obtain it on each platform. A package name
may be None when the platform has no package, in which case the source
build strategy is used as a fallback.
"""
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """Build-from-source recipe used when no system package exists."""

    git_url: str
    build: str   # shell snippet run in the cloned dir; must produce the binary
    binary: str  # path to the built binary, relative to the clone root


@dataclass(frozen=True)
class Backend:
    """An external CLI binary the toolkit orchestrates.

    apt_pkg / termux_pkg are package names, or None when unavailable on
    that platform. When the resolved package is None, `source` is used.
    """

    name: str                     # command to detect on PATH
    apt_pkg: str | None = None
    termux_pkg: str | None = None
    source: Source | None = None


# Registry: key is the logical module name, value is the Backend spec.
BACKENDS: dict[str, Backend] = {
    "abcmidi": Backend(
        name="abc2midi",
        apt_pkg="abcmidi",
        termux_pkg=None,  # not in Termux repos; built from source
        source=Source(
            git_url="https://github.com/sshlien/abcmidi.git",
            build="./configure && make abc2midi",
            binary="abc2midi",
        ),
    ),
    "timidity": Backend(
        name="timidity",
        apt_pkg="timidity",
        termux_pkg="timidity++",  # different package name on Termux
    ),
    "sox": Backend(
        name="sox",
        apt_pkg="sox",
        termux_pkg="sox",
    ),
}

# Profiles: named subsets the installer can target.
PROFILES: dict[str, list[str]] = {
    "minimal": ["abcmidi"],
    "playback": ["abcmidi", "timidity"],
    "full": ["abcmidi", "timidity", "sox"],
}


def is_installed(b: Backend) -> bool:
    """True when the backend binary is resolvable on PATH."""
    return shutil.which(b.name) is not None
