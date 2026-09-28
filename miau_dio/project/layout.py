"""Project layout -- materialize a Project as a self-contained directory.

Scope (task #172, part of redesign #168): a project can live as a
versionable directory the user owns (project.json + tracks/ + patterns/
+ samples/ + renders/ + README.md + .gitignore), independent of the
XDG store that `store.py` uses by default. Both modes coexist: XDG is
the implicit default, an explicit path opts into the directory layout.

The directory is the unit of versioning: musical code, configuration,
patterns, MIDI and metadata belong inside git; renders and caches stay
outside (ignored via .gitignore). This module only creates and reads
the layout -- it does not touch the XDG store.
"""
from __future__ import annotations

import json
import pathlib

from miau_dio.project.model import Project, ProjectError

PROJECT_FILE = "project.json"
README_FILE = "README.md"
GITIGNORE_FILE = ".gitignore"
SUBDIRS = ("tracks", "patterns", "samples", "renders")

_GITIGNORE = """\
# Renders and caches -- regenerable, never versioned.
renders/
*.wav
*.flac
*.tmp
*.bak

# Python bytecode.
__pycache__/
*.py[cod]
"""


class LayoutError(RuntimeError):
    """Raised when the on-disk layout cannot be created or read."""


def _readme(project: Project) -> str:
    lines = [
        f"# {project.name}",
        "",
        f"- tempo: {project.tempo}",
        f"- time_signature: {project.time_signature}",
        f"- key: {project.key}",
        f"- tracks: {len(project.tracks)}",
        "",
    ]
    if project.tracks:
        lines.append("## Tracks")
        lines.append("")
        for t in project.tracks:
            fam = f" ({t.instrument})" if t.instrument else ""
            lines.append(f"- **{t.name}** [{t.type}]{fam}")
        lines.append("")
    return "\n".join(lines)


def _write_text(path: pathlib.Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def create(project: Project, target: str | pathlib.Path) -> pathlib.Path:
    """Materialize `project` at `target` and return the resolved path.

    `target` must not exist (or must be an empty directory) -- refuse to
    overwrite an existing project to avoid silent data loss. Raises
    LayoutError on any conflict.
    """
    if not isinstance(project, Project):
        raise LayoutError(
            f"expected Project, got {type(project).__name__}"
        )
    root = pathlib.Path(target).expanduser().resolve()
    if root.exists():
        if not root.is_dir():
            raise LayoutError(f"target exists and is not a directory: {root}")
        if any(root.iterdir()):
            raise LayoutError(f"target directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (root / sub).mkdir(exist_ok=True)
    _write_text(
        root / PROJECT_FILE,
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False) + "\n",
    )
    _write_text(root / README_FILE, _readme(project))
    _write_text(root / GITIGNORE_FILE, _GITIGNORE)
    return root


def read(target: str | pathlib.Path) -> Project:
    """Load a Project from `target` (a directory containing project.json)."""
    root = pathlib.Path(target).expanduser().resolve()
    if not root.is_dir():
        raise LayoutError(f"not a directory: {root}")
    pfile = root / PROJECT_FILE
    if not pfile.is_file():
        raise LayoutError(f"no {PROJECT_FILE} in {root}")
    try:
        data = json.loads(pfile.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LayoutError(f"corrupt {PROJECT_FILE} at {pfile}: {e}") from e
    try:
        return Project.from_dict(data)
    except ProjectError as e:
        raise LayoutError(f"invalid project data in {pfile}: {e}") from e


def is_project(target: str | pathlib.Path) -> bool:
    """True when `target` looks like a project directory (has project.json)."""
    root = pathlib.Path(target).expanduser()
    return root.is_dir() and (root / PROJECT_FILE).is_file()


__all__ = [
    "GITIGNORE_FILE", "LayoutError", "PROJECT_FILE", "README_FILE", "SUBDIRS",
    "create", "is_project", "read",
]
