"""miau-dio CLI: prototype, store and replay musical ideas from the console."""
import json as _json
import os
import pathlib as _pl
import subprocess
import tempfile as _tempfile

import typer

from miau_dio.backends.backend import BACKENDS, PROFILES, is_installed
from miau_dio.installer.installer import ensure
from miau_dio.pipeline import pipeline
from miau_dio.store import store
from miau_dio.config import config

app = typer.Typer(help="miau-dio: prototype and manage musical ideas in the console", rich_markup_mode=None, pretty_exceptions_enable=False)


@app.command()
def setup(profile: str = typer.Option(None, help="minimal|playback|full")):
    """Install a backend profile (prompts if none given)."""
    if profile is None:
        profile = typer.prompt("Profile to install [minimal/playback/full]",
                               default="playback")
    ensure(PROFILES[profile])
    typer.echo(f"Backend profile '{profile}' ready.")


@app.command()
def status():
    """Show which backends are installed."""
    for name, b in BACKENDS.items():
        mark = "ok" if is_installed(b) else "--"
        typer.echo(f"[{mark}] {name} ({b.name})")


@app.command()
def play(abc: str, out: str = "idea.wav",
         sf: str = typer.Option(None, help="soundfont path")):
    """Render an .abc file to audio."""
    ensure(["abcmidi", "timidity"])
    typer.echo(f"Rendered: {pipeline.render(abc, out, sf)}")


@app.command()
def save(name: str, abc: str,
         tag: list[str] = typer.Option([], "--tag", "-t"),
         note: str = typer.Option("", "--note", "-n")):
    """Store an idea from an .abc file."""
    idea = store.add(name, abc, list(tag), note)
    typer.echo(f"Saved [{idea.id}] {idea.name}")


@app.command(name="list")
def list_ideas(tag: str = typer.Option("", "--tag"),
               query: str = typer.Option("", "--search", "-s"),
               as_json: bool = typer.Option(False, "--json")):
    """List ideas, optionally filtered by tag or search text."""
    items = store.search(query, tag)
    if as_json:
        typer.echo(_json.dumps([i.__dict__ for i in items], ensure_ascii=False))
        return
    for i in items:
        tags = f"  #{' #'.join(i.tags)}" if i.tags else ""
        typer.echo(f"[{i.id}] {i.name}{tags}")


@app.command()
def show(iid: str):
    """Show full detail of one idea."""
    i = store.get(iid)
    typer.echo(f"[{i.id}] {i.name}")
    typer.echo(f"  tags:     {', '.join(i.tags) or '-'}")
    typer.echo(f"  notes:    {i.notes or '-'}")
    typer.echo(f"  created:  {i.created}")
    typer.echo(f"  modified: {i.modified}")


@app.command(name="play-saved")
def play_saved(iid: str, sf: str = typer.Option(None, help="soundfont path"),
               silent: bool = typer.Option(False, "--silent",
                                           help="render only, do not play")):
    """Render (if needed) and play a saved idea through the speakers."""
    out = store.audio_path(iid)
    if out.exists():
        typer.echo(f"(cache) {out}")
    else:
        pipeline.render(str(store.abc_path(iid)), str(out), sf)
        typer.echo(f"Rendered: {out}")
    if not silent:
        from miau_dio.platform.platform import audio_player
        subprocess.run([*audio_player(), str(out)], check=True)


@app.command()
def tag(iid: str,
        add: list[str] = typer.Option([], "--add"),
        rm: list[str] = typer.Option([], "--rm")):
    """Add or remove tags on an idea."""
    i = store.get(iid)
    tags = (set(i.tags) | set(add)) - set(rm)
    store.update(iid, tags=sorted(tags))
    typer.echo(f"tags: {', '.join(sorted(tags)) or '-'}")


@app.command()
def note(iid: str, text: str):
    """Replace the notes on an idea."""
    store.update(iid, notes=text)
    typer.echo("Notes updated.")


@app.command()
def rename(iid: str, new_name: str):
    """Rename an idea (id and artifacts unchanged)."""
    store.update(iid, name=new_name)
    typer.echo(f"Renamed to: {new_name}")


@app.command()
def duplicate(iid: str, name: str = typer.Option(None, "--name")):
    """Duplicate an idea into an independent variation."""
    dup = store.duplicate(iid, name)
    typer.echo(f"Duplicated [{dup.id}] {dup.name}")


@app.command()
def delete(iid: str, yes: bool = typer.Option(False, "--yes", "-y")):
    """Delete an idea and its artifacts."""
    if not yes:
        typer.confirm(f"Delete idea {iid}?", abort=True)
    store.remove(iid)
    typer.echo("Deleted.")


@app.command()
def tags():
    """List all tags currently in use."""
    typer.echo(" ".join(f"#{t}" for t in sorted(store.all_tags())) or "-")


config_app = typer.Typer(help="Manage default key/meter/unit for new ideas")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """Show current defaults for new ideas."""
    for k, v in config.load().items():
        typer.echo(f"{k}: {v}")


@config_app.command("set")
def config_set(field: str, value: str):
    """Set a persistent default (key, meter or unit)."""
    config.set_value(field, value)
    typer.echo(f"{field} = {value}")


@app.command()
def new(name: str,
        key: str = typer.Option(None, "--key", help="ABC key, e.g. Am"),
        meter: str = typer.Option(None, "--meter", help="ABC meter, e.g. 3/4"),
        unit: str = typer.Option(None, "--unit", help="ABC default note length"),
        tag: list[str] = typer.Option([], "--tag", "-t"),
        note: str = typer.Option("", "--note", "-n"),
        bpm: str = typer.Option(None, "--bpm", help="tempo in BPM, e.g. 90"),
        silent: bool = typer.Option(False, "--silent", help="do not play after save")):
    """Create an idea: edit a template, then save and play it.

    key/meter/unit fall back to stored defaults (config) then factory.
    """
    d = config.load()
    key = key or d["key"]
    meter = meter or d["meter"]
    unit = unit or d["unit"]
    bpm = bpm or d["bpm"]
    template = f"X:1\nT:{name}\nM:{meter}\nL:{unit}\nQ:1/4={bpm}\nK:{key}\n"
    editor = os.environ.get("EDITOR") or ("nvim" if __import__("shutil").which("nvim") else "nano")
    with _tempfile.NamedTemporaryFile("w", suffix=".abc", delete=False) as f:
        f.write(template)
        tmp_path = f.name
    subprocess.run([editor, tmp_path], check=True)
    edited = _pl.Path(tmp_path).read_text()
    body = "\n".join(
        l for l in edited.splitlines()
        if l and l[:2] not in ("X:", "T:", "M:", "L:", "K:")
    )
    if not body.strip():
        _pl.Path(tmp_path).unlink(missing_ok=True)
        typer.echo("Empty idea, nothing saved.")
        raise typer.Exit()
    idea = store.add(name, tmp_path, list(tag), note)
    _pl.Path(tmp_path).unlink(missing_ok=True)
    typer.echo(f"Saved [{idea.id}] {idea.name}")
    if not silent:
        ensure(["abcmidi", "timidity"], auto=True)
        out = store.audio_path(idea.id)
        pipeline.render(str(store.abc_path(idea.id)), str(out))
        from miau_dio.platform.platform import audio_player
        subprocess.run([*audio_player(), str(out)], check=True)
