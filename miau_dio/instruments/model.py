"""Instrument model -- the domain entity of the instrument library.

Scope (task #164, part of redesign #239): a single dataclass with
validation, no I/O, no persistence. Persistence lives in
`instruments/library.py` (#165). The GM program number is the canonical
link to the SoundFont renderer; `family` is a free-form label owned by
the user and is NOT persisted as part of the instrument identity.

YAGNI (task #239 notes): no MIDI CC, no per-note params, no effect
chains. Add them only when a real musical need appears.
"""
from __future__ import annotations

from dataclasses import dataclass

GM_PROGRAM_MIN = 0
GM_PROGRAM_MAX = 127
NAME_MAX = 64
FAMILY_MAX = 32


class InstrumentError(ValueError):
    """Raised when an Instrument field fails validation."""


def _validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise InstrumentError(f"name must be a string, got {type(name).__name__}")
    trimmed = name.strip()
    if not trimmed:
        raise InstrumentError("name must not be empty")
    if len(trimmed) > NAME_MAX:
        raise InstrumentError(
            f"name must be <= {NAME_MAX} chars, got {len(trimmed)}"
        )
    return trimmed


def _validate_program(program: int) -> int:
    if isinstance(program, bool):
        raise InstrumentError("program must be an int, not a bool")
    if not isinstance(program, int):
        raise InstrumentError(
            f"program must be an int, got {type(program).__name__}"
        )
    if not (GM_PROGRAM_MIN <= program <= GM_PROGRAM_MAX):
        raise InstrumentError(
            f"program out of GM range [{GM_PROGRAM_MIN}-{GM_PROGRAM_MAX}]: "
            f"{program}"
        )
    return program


def _validate_family(family: str) -> str:
    if not isinstance(family, str):
        raise InstrumentError(
            f"family must be a string, got {type(family).__name__}"
        )
    trimmed = family.strip()
    if len(trimmed) > FAMILY_MAX:
        raise InstrumentError(
            f"family must be <= {FAMILY_MAX} chars, got {len(trimmed)}"
        )
    return trimmed


@dataclass(frozen=True)
class Instrument:
    """A named instrument mapped to a General MIDI program (0-127).

    `family` is a free-form label (e.g. "piano", "strings", "percussion")
    used for grouping. It is optional and left empty by default.
    """

    name: str
    program: int
    family: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validate_name(self.name))
        object.__setattr__(self, "program", _validate_program(self.program))
        object.__setattr__(self, "family", _validate_family(self.family))

    def to_dict(self) -> dict:
        """Serialisable form for the library index."""
        return {"name": self.name, "program": self.program,
                "family": self.family}

    @classmethod
    def from_dict(cls, data: dict) -> "Instrument":
        """Reconstruct from a library index entry; raises on invalid data."""
        if not isinstance(data, dict):
            raise InstrumentError(
                f"instrument entry must be a dict, got {type(data).__name__}"
            )
        missing = {"name", "program"} - data.keys()
        if missing:
            raise InstrumentError(
                f"instrument entry missing fields: {', '.join(sorted(missing))}"
            )
        return cls(
            name=data["name"],
            program=data["program"],
            family=data.get("family", ""),
        )
