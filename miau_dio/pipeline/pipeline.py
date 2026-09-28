"""Render pipeline: abc -> midi -> wav, using the bundled SoundFont."""
import pathlib
import subprocess
import tempfile

from miau_dio.platform.platform import soundfont_path


def _run(cmd: list[str]) -> None:
    """Run a subprocess, raising with captured stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{r.stderr.strip()}")


ENGINES = ("timidity", "fluidsynth")


def _run_timidity(mid: pathlib.Path, out: str, sf: str, gain: float) -> None:
    cmd = ["timidity", str(mid), "-Ow", "-o", out]
    if pathlib.Path(sf).is_file():
        cmd += ["-x", f"soundfont {sf}"]
    if gain:
        cmd += [f"--volume={int(100 + gain * 25)}"]
    _run(cmd)


def _run_fluidsynth(mid: pathlib.Path, out: str, sf: str, gain: float) -> None:
    """Render MIDI to wav offline via fluidsynth.

    `-n` disables MIDI input, `-i` disables the interactive shell, `-F`
    renders to the given file. fluidsynth gain is in [0, 10] with 0.2
    as the library default; our `gain` (shared with timidity, small
    positive compensation) is scaled by 0.1 so gain=6.0 -> 0.6, close
    to the value that was audible in F0 on tx1.
    """
    cmd = ["fluidsynth", "-n", "-i", "-F", out]
    fluid_gain = round(max(0.0, min(gain * 0.1, 10.0)), 2)
    if fluid_gain > 0:
        cmd += ["-g", str(fluid_gain)]
    cmd += [sf, str(mid)]
    _run(cmd)


def render(abc_file: str, out: str = "idea.wav",
           soundfont: str | None = None, gain: float = 6.0,
           engine: str = "timidity") -> str:
    """Render an .abc file to a .wav, returning the output path.

    Uses the bundled SoundFont unless an explicit one is given. `engine`
    selects the synthesis backend: "timidity" (default) or "fluidsynth".
    Both consume the same abc2midi-produced MIDI, so the choice only
    affects the synthesis step.
    """
    abc = pathlib.Path(abc_file)
    if not abc.is_file():
        raise FileNotFoundError(f"abc file not found: {abc_file}")
    if engine not in ENGINES:
        raise ValueError(
            f"unknown engine {engine!r}; expected one of {ENGINES}"
        )
    sf = soundfont or str(soundfont_path())
    with tempfile.TemporaryDirectory() as td:
        mid = pathlib.Path(td) / "idea.mid"
        _run(["abc2midi", str(abc), "-o", str(mid)])
        if engine == "timidity":
            _run_timidity(mid, out, sf, gain)
        else:
            _run_fluidsynth(mid, out, sf, gain)
    return out
