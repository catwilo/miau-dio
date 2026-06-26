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


def render(abc_file: str, out: str = "idea.wav",
           soundfont: str | None = None, gain: float = 6.0) -> str:
    """Render an .abc file to a .wav, returning the output path.

    Uses the bundled SoundFont unless an explicit one is given. A small
    positive gain compensates for the conservative SoundFont volume.
    """
    abc = pathlib.Path(abc_file)
    if not abc.is_file():
        raise FileNotFoundError(f"abc file not found: {abc_file}")
    sf = soundfont or str(soundfont_path())
    with tempfile.TemporaryDirectory() as td:
        mid = pathlib.Path(td) / "idea.mid"
        _run(["abc2midi", str(abc), "-o", str(mid)])
        cmd = ["timidity", str(mid), "-Ow", "-o", out]
        if pathlib.Path(sf).is_file():
            cmd += ["-x", f"soundfont {sf}"]
        if gain:
            cmd += [f"--volume={int(100 + gain * 25)}"]
        _run(cmd)
    return out
