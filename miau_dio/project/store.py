"""Project store -- atomic CRUD over project.json files plus an index.

Scope (task #171, part of redesign #168): persist Project records
(model.py) under XDG_DATA_HOME/miau-dio/projects/<id>/project.json,
with a single index.json providing fast listing. Every write is atomic
(tmp + replace), so a crash never leaves a half-written project. The id
is 8 hex chars from os.urandom, independent of the project name, so
renaming never breaks artifacts and two projects with the same name
created in the same second never collide.

Layout under XDG_DATA_HOME/miau-dio/projects/:
  index.json               {"<id>": {"name": str, "created": str, "modified": str}}
  <id>/project.json        full Project record

Legacy Idea store (miau_dio/store/) is untouched.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil

from miau_dio.project.model import Project, ProjectError


class ProjectStoreError(RuntimeError):
    """Raised when a project store operation cannot be completed."""


def _data_dir() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        "~/.local/share"
    )
    d = pathlib.Path(base) / "miau-dio" / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> pathlib.Path:
    return _data_dir() / "index.json"


def _validate_id(iid: str) -> str:
    """Reject ids that could escape the projects directory."""
    if not isinstance(iid, str) or not iid or "/" in iid or "\\" in iid \
            or iid in (".", ".."):
        raise ProjectStoreError(f"unsafe project id: {iid!r}")
    return iid


def _project_dir(iid: str) -> pathlib.Path:
    return _data_dir() / _validate_id(iid)


def _project_path(iid: str) -> pathlib.Path:
    return _project_dir(iid) / "project.json"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _gen_id() -> str:
    return os.urandom(4).hex()


def _read_json(p: pathlib.Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ProjectStoreError(f"corrupt JSON at {p}: {e}") from e


def _write_json_atomic(p: pathlib.Path, data: dict) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(p)


def _load_index() -> dict[str, dict]:
    idx = _read_json(_index_path())
    if not isinstance(idx, dict):
        raise ProjectStoreError("index.json must contain a JSON object")
    return idx


def _save_index(idx: dict[str, dict]) -> None:
    _write_json_atomic(_index_path(), idx)


def _index_entry(project: Project, created: str, modified: str) -> dict:
    return {
        "name": project.name,
        "created": created,
        "modified": modified,
        "track_count": len(project.tracks),
    }


def exists(iid: str) -> bool:
    _validate_id(iid)
    return iid in _load_index()


def list_projects() -> list[tuple[str, dict]]:
    """Return [(id, index_entry)] sorted by name."""
    idx = _load_index()
    out = [(iid, dict(idx[iid])) for iid in idx]
    out.sort(key=lambda pair: pair[1].get("name", ""))
    return out


def get(iid: str) -> Project:
    _validate_id(iid)
    """Load a Project by id. Raises KeyError when absent."""
    idx = _load_index()
    if iid not in idx:
        raise KeyError(f"project not found: {iid}")
    data = _read_json(_project_path(iid))
    if not data:
        raise ProjectStoreError(
            f"project {iid} listed in index but project.json missing"
        )
    return Project.from_dict(data)


def add(project: Project) -> tuple[str, Project]:
    """Persist a new Project under a fresh id. Returns (id, project)."""
    if not isinstance(project, Project):
        raise ProjectStoreError(
            f"expected Project, got {type(project).__name__}"
        )
    iid = _gen_id()
    while exists(iid):
        iid = _gen_id()
    created = _now()
    modified = created
    stored = Project(
        name=project.name,
        tracks=list(project.tracks),
        tempo=project.tempo,
        time_signature=project.time_signature,
        key=project.key,
        created=created,
        modified=modified,
    )
    d = _project_dir(iid)
    d.mkdir(parents=True, exist_ok=False)
    _write_json_atomic(_project_path(iid), stored.to_dict())
    idx = _load_index()
    idx[iid] = _index_entry(stored, created, modified)
    _save_index(idx)
    return iid, stored


def update(iid: str, **changes) -> Project:
    _validate_id(iid)
    """Replace fields of an existing project, keeping its id."""
    idx = _load_index()
    if iid not in idx:
        raise KeyError(f"project not found: {iid}")
    current = get(iid)
    merged = current.to_dict()
    merged.update(changes)
    merged["created"] = current.created
    merged["modified"] = _now()
    new = Project.from_dict(merged)
    _write_json_atomic(_project_path(iid), new.to_dict())
    idx[iid] = _index_entry(new, new.created, new.modified)
    _save_index(idx)
    return new


def remove(iid: str) -> None:
    _validate_id(iid)
    """Delete a project and its directory. Idempotent."""
    idx = _load_index()
    if iid not in idx:
        return
    del idx[iid]
    _save_index(idx)
    d = _project_dir(iid)
    if d.exists():
        shutil.rmtree(d)


def rename(iid: str, new_name: str) -> Project:
    """Rename a project in place (id stays the same)."""
    return update(iid, name=new_name)


__all__ = [
    "ProjectStoreError",
    "add", "exists", "get", "list_projects", "remove", "rename", "update",
]
