"""Assignment -- write %%MIDI program directives into ABC source.

Scope (task #166, part of redesign #239): given ABC text and an
instrument selection policy, produce new ABC text with `%%MIDI program
<n>` directives placed at the requested positions. Purely text-in,
text-out; no I/O, no filesystem, no audio.

Modes:
  - fixed:  one program for the whole piece, inserted once right after
            the K: header. Pre-existing %%MIDI program directives are
            left untouched (stripping is the caller's concern).
  - random: one random program per note, subject to an optional
            minimum-duration filter. Notes below the filter reuse the
            previous program. The body is rewritten so that every note
            lives on its own line preceded by its directive; this is
            required because %%MIDI directives are line-scoped in ABC.

Fixed mode also accepts at=<note_index> (0-based, post-header): the
directive is placed only before the note at that index. The target
note is moved to its own line so the directive stays line-scoped,
leaving the rest of the source line in place.

Public API:
  annotate(text, mode, *, program=None, programs=None, rng=None,
           min_duration=None, at=None) -> str
  AssignmentError -- raised on invalid input
"""
from __future__ import annotations

import random

from miau_dio.abcparse.tokens import Barline, Note, parse

FIXED = "fixed"
RANDOM = "random"
MODES = (FIXED, RANDOM)


class AssignmentError(ValueError):
    """Raised when an annotation request cannot be satisfied."""


def _duration_value(duration: str) -> float:
    """Interpret an ABC duration string as a float multiplier.

    ABC durations are written as "N", "N/M", "N/", "/M", or "/".
    A bare "N" means N units; "/" alone means 0.5; "N/" means N/2.
    """
    if duration in ("", "1"):
        return 1.0
    if duration == "/":
        return 0.5
    if "/" not in duration:
        try:
            return float(duration)
        except ValueError as e:
            raise AssignmentError(f"bad duration: {duration!r}") from e
    num_s, _, den_s = duration.partition("/")
    num = float(num_s) if num_s else 1.0
    den = float(den_s) if den_s else 2.0
    if den == 0:
        raise AssignmentError(f"zero denominator in duration: {duration!r}")
    return num / den


def _body_start_line(text: str) -> int:
    """Line number of the K: header (1-based); body begins after it."""
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if len(line) >= 2 and line[0] in ("K", "k") and line[1] == ":":
            return n
    raise AssignmentError("no K: header found; cannot locate body")


def _validate_program(p: int) -> int:
    if isinstance(p, bool) or not isinstance(p, int):
        raise AssignmentError(f"program must be an int, got {type(p).__name__}")
    if not (0 <= p <= 127):
        raise AssignmentError(f"program out of GM range [0-127]: {p}")
    return p


def _render_note(note: Note) -> str:
    """Reconstruct the source token for a Note from its parsed fields."""
    octaves = ("'" * note.octave) if note.octave > 0 else ("," * -note.octave)
    return f"{note.accidental}{note.pitch}{octaves}{note.duration}"


def _scan_note_end(line: str, start: int) -> int:
    """Return the exclusive end index of the note token starting at `start`."""
    i = start
    n = len(line)
    while i < n and line[i] in "^_=":
        i += 1
    if i >= n or not line[i].isalpha():
        raise AssignmentError(
            f"internal error: cannot rescan note starting at col {start + 1}"
        )
    i += 1
    while i < n and line[i] in "',":
        i += 1
    while i < n and (line[i].isdigit() or line[i] == "/"):
        i += 1
    return i


def _fixed_annotate(text: str, program: int) -> str:
    _validate_program(program)
    k_line = _body_start_line(text)
    lines = text.splitlines()
    directive = f"%%MIDI program {program}"
    insertion_index = k_line
    while (insertion_index < len(lines)
           and lines[insertion_index].lstrip().startswith("%%MIDI program")):
        insertion_index += 1
    out = lines[:insertion_index] + [directive] + lines[insertion_index:]
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _at_annotate(text: str, program: int, note_index: int) -> str:
    """Insert %%MIDI program <n> immediately before the note at note_index.

    The target note is moved to its own line so the directive is
    line-scoped as ABC requires; the trailing part of the original line
    (if any) stays attached to the note, preserving the visual layout.
    """
    _validate_program(program)
    if isinstance(note_index, bool) or not isinstance(note_index, int):
        raise AssignmentError(
            f"at must be an int, got {type(note_index).__name__}"
        )
    score = parse(text)
    if note_index < 0 or note_index >= len(score.notes):
        raise AssignmentError(
            f"at out of range: {note_index} "
            f"(piece has {len(score.notes)} notes)"
        )
    target = score.notes[note_index]
    lines = text.splitlines()
    line = lines[target.line - 1]
    start = target.col - 1
    end = _scan_note_end(line, start)
    before = line[:start].rstrip()
    note_text = line[start:end]
    after = line[end:]
    new_lines: list[str] = []
    if before:
        new_lines.append(before)
    new_lines.append(f"%%MIDI program {program}")
    new_lines.append(note_text + after)
    lines[target.line - 1:target.line] = new_lines
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _resolve_pool(programs: list[int] | None,
                  program: int | None) -> list[int]:
    """Pool for random mode: explicit list beats single program beats full GM."""
    if programs:
        pool = [_validate_program(p) for p in programs]
    elif program is not None:
        pool = [_validate_program(program)]
    else:
        pool = list(range(128))
    if not pool:
        raise AssignmentError("random mode requires a non-empty program pool")
    return pool


def _random_annotate(text: str, pool: list[int],
                     min_duration: float | None,
                     rng: random.Random) -> str:
    """Rewrite the body inserting a %%MIDI program before each note.

    Notes whose duration value is strictly less than min_duration reuse
    the most recent program. If the very first note falls below the
    filter, a program is still emitted so the piece is not program-less.
    """
    score = parse(text)
    if not score.notes:
        raise AssignmentError("no notes found in body")
    lines = text.splitlines()
    k_line = _body_start_line(text)
    head = lines[:k_line]
    body_events: list[tuple[int, object]] = [
        (n.line, n) for n in score.notes
    ] + [(b.line, b) for b in score.barlines]
    body_events.sort(key=lambda pair: (
        pair[0],
        getattr(pair[1], "col", 0),
    ))
    out: list[str] = list(head)
    last_program: int | None = None
    for _line, ev in body_events:
        if isinstance(ev, Note):
            dur = _duration_value(ev.duration)
            if min_duration is None or dur >= min_duration \
                    or last_program is None:
                last_program = rng.choice(pool)
                out.append(f"%%MIDI program {last_program}")
            out.append(_render_note(ev))
        elif isinstance(ev, Barline):
            out.append(ev.kind)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def annotate(text: str, mode: str, *,
             program: int | None = None,
             programs: list[int] | None = None,
             rng: random.Random | None = None,
             min_duration: float | None = None,
             at: int | None = None) -> str:
    """Return new ABC text with %%MIDI program directives inserted.

    `mode` is "fixed" (one program for the whole piece) or "random"
    (one program per note, optionally filtered by duration).
    `rng` accepts a seeded random.Random for reproducible output.
    `min_duration` is only meaningful in random mode; expressed in the
    same unit as durations ("1" = quarter in 1/4 unit).
    `at` is only valid with fixed mode: 0-based note index (post-header)
    before which the directive is placed, leaving the rest of the file
    untouched.
    """
    if not isinstance(text, str):
        raise AssignmentError(
            f"text must be a string, got {type(text).__name__}"
        )
    # Validate the whole document up front so unsupported ABC syntax is
    # rejected before any output is emitted, regardless of mode.
    parse(text)
    if mode not in MODES:
        raise AssignmentError(f"mode must be one of {MODES}, got {mode!r}")
    if at is not None:
        if mode != FIXED:
            raise AssignmentError("at= is only valid in fixed mode")
        if program is None:
            raise AssignmentError("at= requires program=<0-127>")
        return _at_annotate(text, program, at)
    if mode == FIXED:
        if program is None:
            raise AssignmentError("fixed mode requires program=<0-127>")
        return _fixed_annotate(text, program)
    pool = _resolve_pool(programs, program)
    effective_rng = rng if rng is not None else random.Random()
    return _random_annotate(text, pool, min_duration, effective_rng)


__all__ = ["AssignmentError", "FIXED", "MODES", "RANDOM", "annotate"]
