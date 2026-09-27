"""ABC tokenizer -- strict read-only subset for miau-dio.

Scope (task #163, part of redesign #239): parse exactly what the
instruments/assignment layers need, reject everything else with a clear
error. No semantics beyond recognition; no rewriting; no evaluation.

Supported:
  - Header lines:   X: T: M: L: Q: K:  (single-line, colon-separated)
  - Info lines:     %%MIDI program <0-127>
  - Body notes:     pitch letter [A-Ga-g], accidentals ^ _ =, octave
                    markers ' and ,, durations as digits and '/'.
  - Barlines:       |   ||   |]
  - Whitespace and %-to-end-of-line comments outside header/info lines.

Rejected (raise ABCParseError with clear message):
  - Chords [CEG], tuplets (3, ties -, slurs (), decorations !x!,
    grace notes {}, inline fields [K:...], voice overlay &, repeats
    |: :|, keysig inline [K:...], multi-voice V:, everything not listed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

HEADERS = ("X", "T", "M", "L", "Q", "K")
GM_PROGRAM_MIN = 0
GM_PROGRAM_MAX = 127


class ABCParseError(ValueError):
    """Raised when input contains unsupported ABC syntax."""


@dataclass(frozen=True)
class Header:
    key: str
    value: str
    line: int


@dataclass(frozen=True)
class MidiProgram:
    program: int
    line: int


@dataclass(frozen=True)
class Note:
    pitch: str
    accidental: str
    octave: int
    duration: str
    line: int
    col: int


@dataclass(frozen=True)
class Barline:
    kind: str
    line: int
    col: int


@dataclass
class Score:
    headers: list[Header] = field(default_factory=list)
    midi_programs: list[MidiProgram] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    barlines: list[Barline] = field(default_factory=list)


_FORBIDDEN = {
    "[": "chords or inline fields ([CEG], [K:...])",
    "]": "chords or inline fields ([CEG], [K:...])",
    "(": "slurs or tuplets",
    ")": "slurs or tuplets",
    "-": "ties",
    "~": "rolls/decorations",
    "!": "decorations (!trill!)",
    "{": "grace notes",
    "}": "grace notes",
    "&": "voice overlay",
    ":": "repeats or inline fields (outside header lines)",
    "\\": "line continuation",
}


def _accidental(ch: str) -> bool:
    return ch in "^_="


def _is_pitch(ch: str) -> bool:
    return ch.isalpha() and ch.upper() in "ABCDEFG"


def _is_duration_char(ch: str) -> bool:
    return ch.isdigit() or ch == "/"


def _parse_header(line: str, lineno: int) -> Header | None:
    """Return Header for `X:...` lines, None otherwise."""
    if len(line) >= 2 and line[1] == ":" and line[0].isalpha():
        key = line[0].upper()
        if key not in HEADERS:
            raise ABCParseError(
                f"line {lineno}: unsupported header '{line[0]}:', "
                f"allowed: {' '.join(HEADERS)}"
            )
        return Header(key=key, value=line[2:].strip(), line=lineno)
    return None


def _parse_midi(line: str, lineno: int) -> MidiProgram | None:
    """Return MidiProgram for `%%MIDI program N`, None otherwise."""
    if not line.startswith("%%MIDI"):
        return None
    parts = line.split()
    if len(parts) != 3 or parts[1].lower() != "program":
        raise ABCParseError(
            f"line {lineno}: only '%%MIDI program <0-127>' is supported, "
            f"got: {line!r}"
        )
    try:
        prog = int(parts[2])
    except ValueError:
        raise ABCParseError(
            f"line {lineno}: MIDI program must be an integer, got {parts[2]!r}"
        )
    if not (GM_PROGRAM_MIN <= prog <= GM_PROGRAM_MAX):
        raise ABCParseError(
            f"line {lineno}: MIDI program out of range "
            f"[{GM_PROGRAM_MIN}-{GM_PROGRAM_MAX}]: {prog}"
        )
    return MidiProgram(program=prog, line=lineno)


def _parse_body(line: str, lineno: int) -> Iterable[Note | Barline]:
    """Yield notes and barlines from a body line. Rejects unsupported syntax."""
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "%":
            return
        if ch == "|":
            start = i
            if line[i:i + 2] == "||":
                kind, i = "||", i + 2
            elif line[i:i + 2] == "|]":
                kind, i = "|]", i + 2
            else:
                kind, i = "|", i + 1
            yield Barline(kind=kind, line=lineno, col=start + 1)
            continue
        if ch in _FORBIDDEN:
            raise ABCParseError(
                f"line {lineno} col {i + 1}: unsupported token {ch!r} "
                f"-- {_FORBIDDEN[ch]}"
            )
        if _accidental(ch) or _is_pitch(ch):
            start = i
            acc = ""
            if _accidental(ch):
                acc = ch
                i += 1
                while i < n and _accidental(line[i]):
                    acc += line[i]
                    i += 1
                if i >= n or not _is_pitch(line[i]):
                    raise ABCParseError(
                        f"line {lineno} col {start + 1}: accidental {acc!r} "
                        "not followed by a pitch letter"
                    )
                ch = line[i]
            pitch = ch
            i += 1
            octave = 0
            while i < n and line[i] in "',":
                octave += 1 if line[i] == "'" else -1
                i += 1
            dur = ""
            while i < n and _is_duration_char(line[i]):
                dur += line[i]
                i += 1
            yield Note(
                pitch=pitch, accidental=acc, octave=octave,
                duration=dur or "1", line=lineno, col=start + 1,
            )
            continue
        raise ABCParseError(
            f"line {lineno} col {i + 1}: unsupported character {ch!r}"
        )


def parse(text: str) -> Score:
    """Parse ABC text into a Score. Raises ABCParseError on unsupported input."""
    score = Score()
    in_body = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        if not in_body:
            hdr = _parse_header(line, lineno)
            if hdr is not None:
                score.headers.append(hdr)
                if hdr.key == "K":
                    in_body = True
                continue
            mid = _parse_midi(line, lineno)
            if mid is not None:
                score.midi_programs.append(mid)
                continue
            if line.lstrip().startswith("%"):
                continue
            raise ABCParseError(
                f"line {lineno}: unexpected content before K: header: {line!r}"
            )
        mid = _parse_midi(line, lineno)
        if mid is not None:
            score.midi_programs.append(mid)
            continue
        if line.lstrip().startswith("%"):
            continue
        for tok in _parse_body(line, lineno):
            if isinstance(tok, Note):
                score.notes.append(tok)
            else:
                score.barlines.append(tok)
    return score


def tokens(text: str) -> list:
    """Flat token stream in source order: Header | MidiProgram | Note | Barline.

    Provided as a convenience for callers that need positional ordering;
    `parse()` remains the primary API.
    """
    return _flatten(parse(text))


def _flatten(score: Score) -> list:
    events: list = []
    events.extend(score.headers)
    events.extend(score.midi_programs)
    events.extend(score.barlines)
    events.extend(score.notes)
    events.sort(key=lambda e: (getattr(e, "line", 0), getattr(e, "col", 0)))
    return events
