"""Idea store: persistent CRUD over .abc files plus a JSON metadata index.

Layout under XDG_DATA_HOME/miau-dio:
  abc/<id>.abc      canonical source per idea
  audio/<id>.wav    regenerable render cache
  index.json        metadata index (atomic writes)

The id is stable and name-independent: renaming never breaks artifacts.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
from dataclasses import asdict, dataclass, field


def _data_dir() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = pathlib.Path(base) / "miau-dio"
    (d / "abc").mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(parents=True, exist_ok=True)
    return d


DATA = _data_dir()
INDEX = DATA / "index.json"


@dataclass
class Idea:
    """Metadata record for one musical idea."""

    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created: str = ""
    modified: str = ""
    abc_hash: str = ""


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _load() -> dict[str, dict]:
    if INDEX.exists():
        return json.loads(INDEX.read_text())
    return {}


def _save(idx: dict[str, dict]) -> None:
    """Atomic index write: tmp file then replace."""
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, indent=2, ensure_ascii=False))
    tmp.replace(INDEX)


def _gen_id(name: str) -> str:
    return hashlib.sha1(f"{name}{_now()}".encode()).hexdigest()[:8]


def abc_path(iid: str) -> pathlib.Path:
    return DATA / "abc" / f"{iid}.abc"


def audio_path(iid: str) -> pathlib.Path:
    return DATA / "audio" / f"{iid}.wav"


def add(name: str, abc_file: str, tags: list[str], notes: str) -> Idea:
    """Store a new idea from an .abc source file."""
    src = pathlib.Path(abc_file)
    if not src.is_file():
        raise FileNotFoundError(f"abc file not found: {abc_file}")
    text = src.read_text()
    iid = _gen_id(name)
    abc_path(iid).write_text(text)
    idea = Idea(
        id=iid, name=name, tags=tags, notes=notes,
        created=_now(), modified=_now(),
        abc_hash=hashlib.sha1(text.encode()).hexdigest(),
    )
    idx = _load()
    idx[iid] = asdict(idea)
    _save(idx)
    return idea


def all_ideas() -> list[Idea]:
    return [Idea(**v) for v in _load().values()]


def get(iid: str) -> Idea:
    idx = _load()
    if iid not in idx:
        raise KeyError(f"idea not found: {iid}")
    return Idea(**idx[iid])


def update(iid: str, **changes) -> Idea:
    idx = _load()
    if iid not in idx:
        raise KeyError(f"idea not found: {iid}")
    idx[iid].update(changes)
    idx[iid]["modified"] = _now()
    _save(idx)
    return Idea(**idx[iid])


def remove(iid: str) -> None:
    idx = _load()
    idx.pop(iid, None)
    _save(idx)
    abc_path(iid).unlink(missing_ok=True)
    audio_path(iid).unlink(missing_ok=True)


def duplicate(iid: str, new_name: str | None = None) -> Idea:
    """Copy an idea into an independent variation with a fresh id."""
    src = get(iid)
    text = abc_path(iid).read_text()
    new_id = _gen_id(src.name)
    abc_path(new_id).write_text(text)
    dup = Idea(
        id=new_id,
        name=new_name or f"{src.name} (copy)",
        tags=list(src.tags),
        notes=src.notes,
        created=_now(), modified=_now(),
        abc_hash=src.abc_hash,
    )
    idx = _load()
    idx[new_id] = asdict(dup)
    _save(idx)
    return dup


def search(query: str = "", tag: str = "") -> list[Idea]:
    """Filter ideas by tag and/or substring in name+notes."""
    out = []
    for i in all_ideas():
        if tag and tag not in i.tags:
            continue
        if query and query.lower() not in (i.name + i.notes).lower():
            continue
        out.append(i)
    return out


def all_tags() -> set[str]:
    return {t for i in all_ideas() for t in i.tags}
