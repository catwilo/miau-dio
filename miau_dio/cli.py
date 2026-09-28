"""miau-dio CLI -- instrument library, ideas, assignment, render, playback.

Hierarchy (task #167, redesign #239):
  idea   {new, add, list, show, edit, rename, dup, tag, note, assign, rm}
  instr  {add, list, show, dup, rename, rm}
  family list
  play   {file, idea}
  config {show, set}
  backend {setup, status, selftest}

Storage layout is unchanged from the previous CLI: ideas live under
XDG_DATA_HOME/miau-dio/{abc,audio}/index.json (store.py) and the
instrument library under XDG_DATA_HOME/miau-dio/instruments/ (library.py).
There is no on-disk migration -- the change is a clean CLI surface
without aliases, as specified by task #239.
"""
from __future__ import annotations

import argparse
import hashlib
import json as _json
import os
import pathlib
import random as _random
import shutil
import subprocess
import sys
import tempfile

from miau_dio.assignment import annotate as _ann
from miau_dio.backends.backend import BACKENDS, PROFILES, is_installed
from miau_dio.config import config
from miau_dio.instruments import library as _lib
from miau_dio.instruments.model import Instrument, InstrumentError
from miau_dio.installer.installer import ensure
from miau_dio.pipeline import pipeline
from miau_dio.store import store
from miau_dio.project import store as _pstore
from miau_dio.project.model import Project, ProjectError as _ProjectError, Track


# ---- helpers ---------------------------------------------------------------

def _pick_editor() -> str:
    return os.environ.get("EDITOR") or ("nvim" if shutil.which("nvim") else "nano")


def _play(path: str) -> None:
    from miau_dio.platform.platform import audio_player
    subprocess.run([*audio_player(), path], check=True)


def _write_atomic(path: pathlib.Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _library_programs() -> list[int]:
    """Programs available for --random: the whole user instrument library."""
    instrs = _lib.list_instruments()
    if not instrs:
        raise SystemExit(
            "library is empty: create instruments with 'miau-dio instr add' "
            "before using --random"
        )
    return [i.program for i in instrs]


# ---- idea handlers ---------------------------------------------------------

def cmd_idea_new(a):
    d = config.load()
    key = a.key or d["key"]
    meter = a.meter or d["meter"]
    unit = a.unit or d["unit"]
    bpm = a.bpm or d["bpm"]
    template = f"X:1\nT:{a.name}\nM:{meter}\nL:{unit}\nQ:1/4={bpm}\nK:{key}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".abc", delete=False) as f:
        f.write(template)
        tmp_path = f.name
    subprocess.run([_pick_editor(), tmp_path], check=True)
    edited = pathlib.Path(tmp_path).read_text()
    body = "\n".join(l for l in edited.splitlines()
                     if l and l[:2] not in ("X:", "T:", "M:", "L:", "Q:", "K:"))
    if not body.strip():
        pathlib.Path(tmp_path).unlink(missing_ok=True)
        print("Empty idea, nothing saved.")
        return
    idea = store.add(a.name, tmp_path, a.tag, a.note)
    pathlib.Path(tmp_path).unlink(missing_ok=True)
    print(f"Saved [{idea.id}] {idea.name}")
    if not a.silent:
        ensure(["abcmidi", "timidity"], auto=True)
        out = store.audio_path(idea.id)
        pipeline.render(str(store.abc_path(idea.id)), str(out))
        _play(str(out))


def cmd_idea_add(a):
    idea = store.add(a.name, a.abc, a.tag, a.note)
    print(f"Saved [{idea.id}] {idea.name}")


def cmd_idea_list(a):
    items = store.search(a.search or "", a.tag or "")
    if a.json:
        print(_json.dumps([i.__dict__ for i in items], ensure_ascii=False))
        return
    for i in items:
        tags = f"  #{' #'.join(i.tags)}" if i.tags else ""
        print(f"[{i.id}] {i.name}{tags}")


def cmd_idea_show(a):
    i = store.get(a.id)
    print(f"[{i.id}] {i.name}")
    print(f"  tags:     {', '.join(i.tags) or '-'}")
    print(f"  notes:    {i.notes or '-'}")
    print(f"  created:  {i.created}")
    print(f"  modified: {i.modified}")


def cmd_idea_edit(a):
    i = store.get(a.id)
    abc = store.abc_path(a.id)
    before = abc.read_text()
    subprocess.run([_pick_editor(), str(abc)], check=True)
    after = abc.read_text()
    if after != before:
        store.audio_path(a.id).unlink(missing_ok=True)
        store.update(a.id,
                     abc_hash=hashlib.sha1(after.encode()).hexdigest())
        print(f"[{a.id}] {i.name} updated (audio cache cleared)")
    else:
        print(f"[{a.id}] {i.name} unchanged")


def cmd_idea_rename(a):
    store.update(a.id, name=a.new_name)
    print(f"Renamed to: {a.new_name}")


def cmd_idea_dup(a):
    dup = store.duplicate(a.id, a.name)
    print(f"Duplicated [{dup.id}] {dup.name}")


def cmd_idea_tag(a):
    i = store.get(a.id)
    tags = (set(i.tags) | set(a.add)) - set(a.rm)
    store.update(a.id, tags=sorted(tags))
    print(f"tags: {', '.join(sorted(tags)) or '-'}")


def cmd_idea_note(a):
    store.update(a.id, notes=a.text)
    print("Notes updated.")


def cmd_idea_assign(a):
    """Persist a fixed %%MIDI program directive into the idea's .abc."""
    idea = store.get(a.id)
    abc = store.abc_path(a.id)
    text = abc.read_text()
    try:
        new_text = _ann.annotate(text, _ann.FIXED,
                                 program=a.program, at=a.at)
    except _ann.AssignmentError as e:
        raise SystemExit(f"assign failed: {e}")
    _write_atomic(abc, new_text)
    store.audio_path(a.id).unlink(missing_ok=True)
    store.update(a.id,
                 abc_hash=hashlib.sha1(new_text.encode()).hexdigest())
    target = "top of body" if a.at is None else f"note {a.at}"
    print(f"[{idea.id}] {idea.name}: program {a.program} at {target}")


def cmd_idea_rm(a):
    if not a.yes:
        if input(f"Delete idea {a.id}? [y/N] ").lower() != "y":
            return
    store.remove(a.id)
    print("Deleted.")


# ---- instr handlers --------------------------------------------------------

def cmd_instr_add(a):
    try:
        instr = Instrument(name=a.name, program=a.program, family=a.family or "")
    except InstrumentError as e:
        raise SystemExit(f"instr add failed: {e}")
    try:
        _lib.add(instr)
    except _lib.LibraryError as e:
        raise SystemExit(f"instr add failed: {e}")
    print(f"Added instrument: {instr.name} (program {instr.program})")


def cmd_instr_list(a):
    items = _lib.list_instruments()
    if a.json:
        print(_json.dumps([i.to_dict() for i in items], ensure_ascii=False))
        return
    for i in items:
        fam = f"  [{i.family}]" if i.family else ""
        print(f"{i.name}  program={i.program}{fam}")


def cmd_instr_show(a):
    try:
        i = _lib.get(a.name)
    except KeyError as e:
        raise SystemExit(str(e))
    print(f"name:    {i.name}")
    print(f"program: {i.program}")
    print(f"family:  {i.family or '-'}")


def cmd_instr_dup(a):
    try:
        dup = _lib.duplicate(a.name, a.new_name)
    except (KeyError, _lib.LibraryError) as e:
        raise SystemExit(f"instr dup failed: {e}")
    print(f"Duplicated: {dup.name}")


def cmd_instr_rename(a):
    try:
        moved = _lib.rename(a.old, a.new)
    except (KeyError, _lib.LibraryError) as e:
        raise SystemExit(f"instr rename failed: {e}")
    print(f"Renamed: {a.old} -> {moved.name}")


def cmd_instr_rm(a):
    if not a.yes:
        if input(f"Delete instrument {a.name}? [y/N] ").lower() != "y":
            return
    _lib.remove(a.name)
    print("Deleted.")


# ---- family ----------------------------------------------------------------

def cmd_family_list(a):
    fams = _lib.families()
    if not fams:
        print("-")
        return
    for f in fams:
        print(f)


# ---- project ---------------------------------------------------------------

def cmd_project_new(a):
    tracks = []
    for spec in (a.track or []):
        parts = spec.split(":", 2)
        if len(parts) < 2:
            raise SystemExit(
                f"--track must be name:type[:content], got {spec!r}"
            )
        name = parts[0]
        ttype = parts[1]
        content = parts[2] if len(parts) > 2 else ""
        try:
            tracks.append(Track(name=name, type=ttype, content=content))
        except _ProjectError as e:
            raise SystemExit(f"track {name!r} invalid: {e}")
    try:
        project = Project(
            name=a.name,
            tracks=tracks,
            tempo=a.tempo if a.tempo is not None else 120.0,
            time_signature=a.meter or "4/4",
            key=a.key or "C",
        )
    except _ProjectError as e:
        raise SystemExit(f"project new failed: {e}")
    iid, stored = _pstore.add(project)
    print(f"Created [{iid}] {stored.name} ({len(stored.tracks)} tracks)")


def cmd_project_list(a):
    items = _pstore.list_projects()
    if a.json:
        print(_json.dumps(
            [{"id": i, **e} for i, e in items], ensure_ascii=False
        ))
        return
    for iid, entry in items:
        tc = entry.get("track_count", 0)
        print(f"[{iid}] {entry['name']}  ({tc} tracks)")


def cmd_project_show(a):
    try:
        p = _pstore.get(a.id)
    except (KeyError, _pstore.ProjectStoreError) as e:
        raise SystemExit(str(e))
    print(f"[{a.id}] {p.name}")
    print(f"  tempo:          {p.tempo}")
    print(f"  time_signature: {p.time_signature}")
    print(f"  key:            {p.key}")
    print(f"  created:        {p.created}")
    print(f"  modified:       {p.modified}")
    print(f"  tracks:         {len(p.tracks)}")
    for i, t in enumerate(p.tracks):
        print(f"    [{i}] {t.name}  type={t.type}  "
              f"instrument={t.instrument or '-'}  "
              f"vol={t.volume}  pan={t.pan}")


def cmd_project_rm(a):
    if not a.yes:
        if input(f"Delete project {a.id}? [y/N] ").lower() != "y":
            return
    _pstore.remove(a.id)
    print("Deleted.")

# ---- play ------------------------------------------------------------------

def cmd_play_file(a):
    ensure(["abcmidi", "timidity"], auto=True)
    print(f"Rendered: {pipeline.render(a.abc, a.out, a.sf)}")


def cmd_play_idea(a):
    """Render and play a saved idea, optionally with a random override."""
    idea = store.get(a.id)
    src_abc = store.abc_path(a.id)
    if not src_abc.is_file():
        raise SystemExit(f"idea {a.id} has no .abc on disk")

    if a.random:
        try:
            pool = _library_programs()
        except SystemExit:
            raise
        rng = _random.Random(a.seed) if a.seed is not None else _random.Random()
        text = src_abc.read_text()
        try:
            new_text = _ann.annotate(text, _ann.RANDOM,
                                     programs=pool,
                                     rng=rng,
                                     min_duration=a.min_duration)
        except _ann.AssignmentError as e:
            raise SystemExit(f"play --random failed: {e}")
        with tempfile.NamedTemporaryFile("w", suffix=".abc",
                                         delete=False) as f:
            f.write(new_text)
            tmp_abc = f.name
        with tempfile.NamedTemporaryFile(suffix=".wav",
                                         delete=False) as f:
            tmp_wav = f.name
        try:
            ensure(["abcmidi", "timidity"], auto=True)
            pipeline.render(tmp_abc, tmp_wav, a.sf)
            print(f"Rendered (random): {tmp_wav}")
            if not a.silent:
                _play(tmp_wav)
        finally:
            pathlib.Path(tmp_abc).unlink(missing_ok=True)
            pathlib.Path(tmp_wav).unlink(missing_ok=True)
        return

    out = store.audio_path(a.id)
    if out.exists():
        print(f"(cache) {out}")
    else:
        pipeline.render(str(src_abc), str(out), a.sf)
        print(f"Rendered: {out}")
    if not a.silent:
        _play(str(out))


# ---- config ----------------------------------------------------------------

def cmd_config_show(a):
    for k, v in config.load().items():
        print(f"{k}: {v}")


def cmd_config_set(a):
    config.set_value(a.field, a.value)
    print(f"{a.field} = {a.value}")


# ---- backend ---------------------------------------------------------------

def cmd_backend_setup(a):
    profile = a.profile or input("Profile [minimal/playback/full]: ") or "playback"
    ensure(PROFILES[profile], auto=True)
    print(f"Backend profile '{profile}' ready.")


def cmd_backend_status(a):
    for name, b in BACKENDS.items():
        print(f"[{'ok' if is_installed(b) else '--'}] {name} ({b.name})")


def cmd_backend_selftest(a):
    """Exercise every operation on a throwaway idea, then clean up."""
    results = []

    def check(label, fn):
        try:
            fn()
            results.append((label, True, ""))
        except Exception as e:  # noqa: BLE001
            results.append((label, False, str(e)))

    state = {}

    def _save():
        f = tempfile.NamedTemporaryFile("w", suffix=".abc", delete=False)
        f.write("X:1\nT:selftest\nM:4/4\nL:1/4\nK:C\nC E G c|\n")
        f.close()
        state["abc"] = f.name
        idea = store.add("__selftest__", f.name, ["t1", "t2"], "note")
        state["id"] = idea.id

    check("save", _save)
    check("get/show", lambda: store.get(state["id"]))
    check("tag add/rm", lambda: store.update(
        state["id"], tags=sorted((set(["t1", "t2"]) | {"t3"}) - {"t2"})))
    check("note", lambda: store.update(state["id"], notes="updated"))
    check("rename", lambda: store.update(state["id"], name="__selftest_renamed__"))
    check("search", lambda: store.search("selftest", ""))
    check("all_tags", lambda: store.all_tags())

    def _dup():
        d = store.duplicate(state["id"], "__selftest_dup__")
        state["dup"] = d.id
    check("duplicate", _dup)

    check("config load", lambda: config.load())
    check("config set/restore", lambda: (
        config.set_value("bpm", config.get("bpm"))))

    def _assign():
        abc = store.abc_path(state["id"])
        text = abc.read_text()
        new_text = _ann.annotate(text, _ann.FIXED, program=40)
        _write_atomic(abc, new_text)
    check("assign fixed", _assign)

    def _assign_at():
        abc = store.abc_path(state["id"])
        text = abc.read_text()
        new_text = _ann.annotate(text, _ann.FIXED, program=0, at=0)
        _write_atomic(abc, new_text)
    check("assign at", _assign_at)

    def _instr_roundtrip():
        i = Instrument(name="__selftest_instr__", program=42, family="test")
        _lib.add(i)
        _lib.get("__selftest_instr__")
        _lib.rename("__selftest_instr__", "__selftest_instr2__")
        _lib.remove("__selftest_instr2__")
    check("instr roundtrip", _instr_roundtrip)

    if a.full:
        def _render():
            ensure(["abcmidi", "timidity"], auto=True)
            out = store.audio_path(state["id"])
            pipeline.render(str(store.abc_path(state["id"])), str(out))
            if not out.exists() or out.stat().st_size < 1000:
                raise RuntimeError("render produced no audio")
        check("render (full)", _render)

    for key in ("id", "dup"):
        if key in state:
            try:
                store.remove(state[key])
            except Exception:  # noqa: BLE001
                pass
    if "abc" in state:
        pathlib.Path(state["abc"]).unlink(missing_ok=True)

    ok = sum(1 for _, p, _ in results if p)
    for label, passed, err in results:
        mark = "ok  " if passed else "FAIL"
        line = f"[{mark}] {label}"
        if err:
            line += f"  -> {err}"
        print(line)
    print(f"{ok}/{len(results)} passed")
    if ok != len(results):
        raise SystemExit(1)


# ---- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="miau-dio",
        description="instrument library + musical ideas + render",
    )
    top = p.add_subparsers(dest="cmd", required=True)

    # ---- idea --------------------------------------------------------------
    idea = top.add_parser("idea", help="manage musical ideas")
    isub = idea.add_subparsers(dest="idea_cmd", required=True)

    s = isub.add_parser("new", help="create an idea: edit, save, play")
    s.add_argument("name")
    s.add_argument("--key", default=None)
    s.add_argument("--meter", default=None)
    s.add_argument("--unit", default=None)
    s.add_argument("--bpm", default=None)
    s.add_argument("-t", "--tag", action="append", default=[])
    s.add_argument("-n", "--note", default="")
    s.add_argument("--silent", action="store_true")
    s.set_defaults(func=cmd_idea_new)

    s = isub.add_parser("add", help="store an idea from an existing .abc")
    s.add_argument("name")
    s.add_argument("abc")
    s.add_argument("-t", "--tag", action="append", default=[])
    s.add_argument("-n", "--note", default="")
    s.set_defaults(func=cmd_idea_add)

    s = isub.add_parser("list", help="list ideas")
    s.add_argument("--tag", default="")
    s.add_argument("-s", "--search", default="")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_idea_list)

    s = isub.add_parser("show", help="show one idea")
    s.add_argument("id")
    s.set_defaults(func=cmd_idea_show)

    s = isub.add_parser("edit", help="open an idea in the editor")
    s.add_argument("id")
    s.set_defaults(func=cmd_idea_edit)

    s = isub.add_parser("rename", help="rename an idea")
    s.add_argument("id")
    s.add_argument("new_name")
    s.set_defaults(func=cmd_idea_rename)

    s = isub.add_parser("dup", help="duplicate an idea")
    s.add_argument("id")
    s.add_argument("--name", default=None)
    s.set_defaults(func=cmd_idea_dup)

    s = isub.add_parser("tag", help="add or remove tags")
    s.add_argument("id")
    s.add_argument("--add", action="append", default=[])
    s.add_argument("--rm", action="append", default=[])
    s.set_defaults(func=cmd_idea_tag)

    s = isub.add_parser("note", help="replace notes")
    s.add_argument("id")
    s.add_argument("text")
    s.set_defaults(func=cmd_idea_note)

    s = isub.add_parser(
        "assign",
        help="write a MIDI program directive into the idea's .abc",
    )
    s.add_argument("id")
    s.add_argument("--program", type=int, required=True,
                   help="GM program 0-127")
    s.add_argument("--at", type=int, default=None,
                   help="0-based note index; omit to set the whole piece")
    s.set_defaults(func=cmd_idea_assign)

    s = isub.add_parser("rm", help="delete an idea")
    s.add_argument("id")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_idea_rm)

    # ---- instr -------------------------------------------------------------
    instr = top.add_parser("instr", help="manage the instrument library")
    nsub = instr.add_subparsers(dest="instr_cmd", required=True)

    s = nsub.add_parser("add", help="register a new instrument")
    s.add_argument("name")
    s.add_argument("program", type=int, help="GM program 0-127")
    s.add_argument("--family", default="")
    s.set_defaults(func=cmd_instr_add)

    s = nsub.add_parser("list", help="list instruments")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_instr_list)

    s = nsub.add_parser("show", help="show one instrument")
    s.add_argument("name")
    s.set_defaults(func=cmd_instr_show)

    s = nsub.add_parser("dup", help="duplicate an instrument")
    s.add_argument("name")
    s.add_argument("--name", dest="new_name", default=None)
    s.set_defaults(func=cmd_instr_dup)

    s = nsub.add_parser("rename", help="rename an instrument")
    s.add_argument("old")
    s.add_argument("new")
    s.set_defaults(func=cmd_instr_rename)

    s = nsub.add_parser("rm", help="delete an instrument")
    s.add_argument("name")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_instr_rm)

    # ---- family ------------------------------------------------------------
    fam = top.add_parser("family", help="instrument families")
    fsub = fam.add_subparsers(dest="family_cmd", required=True)
    s = fsub.add_parser("list", help="list distinct family labels")
    s.set_defaults(func=cmd_family_list)

    # ---- project -----------------------------------------------------------
    proj = top.add_parser("project", help="manage musical projects")
    pjsub = proj.add_subparsers(dest="project_cmd", required=True)

    s = pjsub.add_parser("new", help="create a project")
    s.add_argument("name")
    s.add_argument("--tempo", type=float, default=None)
    s.add_argument("--meter", default=None, help="time signature, e.g. 4/4")
    s.add_argument("--key", default=None)
    s.add_argument("--track", action="append", default=[],
                   help="name:type[:content]; repeatable")
    s.set_defaults(func=cmd_project_new)

    s = pjsub.add_parser("list", help="list projects")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_project_list)

    s = pjsub.add_parser("show", help="show one project")
    s.add_argument("id")
    s.set_defaults(func=cmd_project_show)

    s = pjsub.add_parser("rm", help="delete a project")
    s.add_argument("id")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_project_rm)

    # ---- play --------------------------------------------------------------
    play = top.add_parser("play", help="render and play")
    psub = play.add_subparsers(dest="play_cmd", required=True)

    s = psub.add_parser("file", help="render an .abc file")
    s.add_argument("abc")
    s.add_argument("--out", default="idea.wav")
    s.add_argument("--sf", default=None)
    s.set_defaults(func=cmd_play_file)

    s = psub.add_parser("idea", help="render and play a saved idea")
    s.add_argument("id")
    s.add_argument("--sf", default=None)
    s.add_argument("--silent", action="store_true")
    s.add_argument("--random", action="store_true",
                   help="override programs randomly from the library")
    s.add_argument("--seed", type=int, default=None,
                   help="seed for --random (reproducible output)")
    s.add_argument("--min-duration", type=float, default=None,
                   help="notes shorter than this reuse the previous program")
    s.set_defaults(func=cmd_play_idea)

    # ---- config ------------------------------------------------------------
    cfg = top.add_parser("config", help="manage defaults for new ideas")
    csub = cfg.add_subparsers(dest="config_cmd", required=True)
    s = csub.add_parser("show", help="show current defaults")
    s.set_defaults(func=cmd_config_show)
    s = csub.add_parser("set", help="set a default (key/meter/unit/bpm)")
    s.add_argument("field")
    s.add_argument("value")
    s.set_defaults(func=cmd_config_set)

    # ---- backend -----------------------------------------------------------
    be = top.add_parser("backend", help="external audio backends")
    bsub = be.add_subparsers(dest="backend_cmd", required=True)

    s = bsub.add_parser("setup", help="install a backend profile")
    s.add_argument("--profile", choices=list(PROFILES))
    s.set_defaults(func=cmd_backend_setup)

    s = bsub.add_parser("status", help="show installed backends")
    s.set_defaults(func=cmd_backend_status)

    s = bsub.add_parser("selftest", help="run an internal self-check")
    s.add_argument("--full", action="store_true",
                   help="also test audio render")
    s.set_defaults(func=cmd_backend_selftest)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
