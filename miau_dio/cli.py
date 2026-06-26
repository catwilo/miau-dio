"""miau-dio CLI: prototype, store and replay musical ideas from the console."""
import json as _json
import subprocess

import typer

from miau_dio.backends.backend import BACKENDS, PROFILES, is_installed
from miau_dio.installer.installer import ensure
from miau_dio.pipeline import pipeline
from miau_dio.store import store

app = typer.Typer(help="miau-dio: prototype and manage musical ideas in the console")


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
