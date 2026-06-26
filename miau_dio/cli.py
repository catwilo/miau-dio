"""miau-dio CLI (argparse, zero external deps): prototype and manage ideas."""
import argparse
import json as _json
import os
import pathlib as _pl
import shutil
import subprocess
import sys
import tempfile as _tempfile

from miau_dio.backends.backend import BACKENDS, PROFILES, is_installed
from miau_dio.installer.installer import ensure
from miau_dio.pipeline import pipeline
from miau_dio.store import store
from miau_dio.config import config


def _pick_editor() -> str:
    return os.environ.get("EDITOR") or ("nvim" if shutil.which("nvim") else "nano")


def _play(path: str) -> None:
    from miau_dio.platform.platform import audio_player
    subprocess.run([*audio_player(), path], check=True)


# ---- command handlers -------------------------------------------------------

def cmd_setup(a):
    profile = a.profile or input("Profile [minimal/playback/full]: ") or "playback"
    ensure(PROFILES[profile], auto=True)
    print(f"Backend profile '{profile}' ready.")


def cmd_status(a):
    for name, b in BACKENDS.items():
        print(f"[{'ok' if is_installed(b) else '--'}] {name} ({b.name})")


def cmd_play(a):
    ensure(["abcmidi", "timidity"], auto=True)
    print(f"Rendered: {pipeline.render(a.abc, a.out, a.sf)}")


def cmd_save(a):
    idea = store.add(a.name, a.abc, a.tag, a.note)
    print(f"Saved [{idea.id}] {idea.name}")


def cmd_list(a):
    items = store.search(a.search or "", a.tag or "")
    if a.json:
        print(_json.dumps([i.__dict__ for i in items], ensure_ascii=False))
        return
    for i in items:
        tags = f"  #{' #'.join(i.tags)}" if i.tags else ""
        print(f"[{i.id}] {i.name}{tags}")


def cmd_show(a):
    i = store.get(a.id)
    print(f"[{i.id}] {i.name}")
    print(f"  tags:     {', '.join(i.tags) or '-'}")
    print(f"  notes:    {i.notes or '-'}")
    print(f"  created:  {i.created}")
    print(f"  modified: {i.modified}")


def cmd_play_saved(a):
    out = store.audio_path(a.id)
    if out.exists():
        print(f"(cache) {out}")
    else:
        pipeline.render(str(store.abc_path(a.id)), str(out), a.sf)
        print(f"Rendered: {out}")
    if not a.silent:
        _play(str(out))


def cmd_tag(a):
    i = store.get(a.id)
    tags = (set(i.tags) | set(a.add)) - set(a.rm)
    store.update(a.id, tags=sorted(tags))
    print(f"tags: {', '.join(sorted(tags)) or '-'}")


def cmd_note(a):
    store.update(a.id, notes=a.text)
    print("Notes updated.")


def cmd_rename(a):
    store.update(a.id, name=a.new_name)
    print(f"Renamed to: {a.new_name}")


def cmd_duplicate(a):
    dup = store.duplicate(a.id, a.name)
    print(f"Duplicated [{dup.id}] {dup.name}")


def cmd_delete(a):
    if not a.yes:
        if input(f"Delete idea {a.id}? [y/N] ").lower() != "y":
            return
    store.remove(a.id)
    print("Deleted.")


def cmd_tags(a):
    print(" ".join(f"#{t}" for t in sorted(store.all_tags())) or "-")


def cmd_config_show(a):
    for k, v in config.load().items():
        print(f"{k}: {v}")


def cmd_config_set(a):
    config.set_value(a.field, a.value)
    print(f"{a.field} = {a.value}")


def cmd_new(a):
    d = config.load()
    key = a.key or d["key"]
    meter = a.meter or d["meter"]
    unit = a.unit or d["unit"]
    bpm = a.bpm or d["bpm"]
    template = f"X:1\nT:{a.name}\nM:{meter}\nL:{unit}\nQ:1/4={bpm}\nK:{key}\n"
    with _tempfile.NamedTemporaryFile("w", suffix=".abc", delete=False) as f:
        f.write(template)
        tmp_path = f.name
    subprocess.run([_pick_editor(), tmp_path], check=True)
    edited = _pl.Path(tmp_path).read_text()
    body = "\n".join(l for l in edited.splitlines()
                     if l and l[:2] not in ("X:", "T:", "M:", "L:", "Q:", "K:"))
    if not body.strip():
        _pl.Path(tmp_path).unlink(missing_ok=True)
        print("Empty idea, nothing saved.")
        return
    idea = store.add(a.name, tmp_path, a.tag, a.note)
    _pl.Path(tmp_path).unlink(missing_ok=True)
    print(f"Saved [{idea.id}] {idea.name}")
    if not a.silent:
        ensure(["abcmidi", "timidity"], auto=True)
        out = store.audio_path(idea.id)
        pipeline.render(str(store.abc_path(idea.id)), str(out))
        _play(str(out))


def cmd_edit(a):
    """Open an idea's .abc in the editor; invalidates audio cache on save."""
    i = store.get(a.id)
    abc = store.abc_path(a.id)
    editor = os.environ.get("EDITOR") or ("nvim" if shutil.which("nvim") else "nano")
    before = abc.read_text()
    subprocess.run([editor, str(abc)], check=True)
    after = abc.read_text()
    if after != before:
        store.audio_path(a.id).unlink(missing_ok=True)
        print(f"[{a.id}] {i.name} updated (audio cache cleared)")
    else:
        print(f"[{a.id}] {i.name} unchanged")


def cmd_selftest(a):
    """Exercise every operation on a throwaway idea, then clean up."""
    import tempfile
    results = []

    def check(label, fn):
        try:
            fn()
            results.append((label, True, ""))
        except Exception as e:
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

    if a.full:
        def _render():
            ensure(["abcmidi", "timidity"], auto=True)
            out = store.audio_path(state["id"])
            pipeline.render(str(store.abc_path(state["id"])), str(out))
            if not out.exists() or out.stat().st_size < 1000:
                raise RuntimeError("render produced no audio")
        check("render (full)", _render)

    # cleanup
    for key in ("id", "dup"):
        if key in state:
            try:
                store.remove(state[key])
            except Exception:
                pass
    if "abc" in state:
        import pathlib
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


# ---- parser -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="miau-dio",
                                description="prototype and manage musical ideas")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="install a backend profile")
    s.add_argument("--profile", choices=list(PROFILES))
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("status", help="show installed backends")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("play", help="render an .abc file to audio")
    s.add_argument("abc")
    s.add_argument("--out", default="idea.wav")
    s.add_argument("--sf", default=None)
    s.set_defaults(func=cmd_play)

    s = sub.add_parser("save", help="store an idea from an .abc file")
    s.add_argument("name")
    s.add_argument("abc")
    s.add_argument("-t", "--tag", action="append", default=[])
    s.add_argument("-n", "--note", default="")
    s.set_defaults(func=cmd_save)

    s = sub.add_parser("list", help="list ideas")
    s.add_argument("--tag", default="")
    s.add_argument("-s", "--search", default="")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one idea")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("play-saved", help="render and play a saved idea")
    s.add_argument("id")
    s.add_argument("--sf", default=None)
    s.add_argument("--silent", action="store_true")
    s.set_defaults(func=cmd_play_saved)

    s = sub.add_parser("tag", help="add or remove tags")
    s.add_argument("id")
    s.add_argument("--add", action="append", default=[])
    s.add_argument("--rm", action="append", default=[])
    s.set_defaults(func=cmd_tag)

    s = sub.add_parser("note", help="replace notes")
    s.add_argument("id")
    s.add_argument("text")
    s.set_defaults(func=cmd_note)

    s = sub.add_parser("rename", help="rename an idea")
    s.add_argument("id")
    s.add_argument("new_name")
    s.set_defaults(func=cmd_rename)

    s = sub.add_parser("duplicate", help="duplicate an idea")
    s.add_argument("id")
    s.add_argument("--name", default=None)
    s.set_defaults(func=cmd_duplicate)

    s = sub.add_parser("delete", help="delete an idea")
    s.add_argument("id")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("tags", help="list all tags")
    s.set_defaults(func=cmd_tags)

    s = sub.add_parser("new", help="create an idea: edit, save, play")
    s.add_argument("name")
    s.add_argument("--key", default=None)
    s.add_argument("--meter", default=None)
    s.add_argument("--unit", default=None)
    s.add_argument("--bpm", default=None)
    s.add_argument("-t", "--tag", action="append", default=[])
    s.add_argument("-n", "--note", default="")
    s.add_argument("--silent", action="store_true")
    s.set_defaults(func=cmd_new)

    cfg = sub.add_parser("config", help="manage defaults for new ideas")
    cfgsub = cfg.add_subparsers(dest="config_cmd", required=True)
    cs = cfgsub.add_parser("show", help="show current defaults")
    cs.set_defaults(func=cmd_config_show)
    cset = cfgsub.add_parser("set", help="set a default (key/meter/unit/bpm)")
    cset.add_argument("field")
    cset.add_argument("value")
    cset.set_defaults(func=cmd_config_set)

    s = sub.add_parser("edit", help="open an idea in the editor")
    s.add_argument("id")
    s.set_defaults(func=cmd_edit)

    s = sub.add_parser("selftest", help="run an internal self-check")
    s.add_argument("--full", action="store_true", help="also test audio render")
    s.set_defaults(func=cmd_selftest)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
