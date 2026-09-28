"""Project/Track domain model -- the new core entity of miau-dio.

Scope (task #171, part of redesign #168): introduces a Project that owns
a list of Tracks, decoupled from any specific engine. A Track carries
its own musical identity (type, instrument, content, timing, volume,
pan, effects) so that Project never has to interpret the serialized
form of `content`. Validation lives in __post_init__; no I/O here.
Persistence lives in `project/store.py`. Legacy `Idea` (idea/abc + tags)
remains untouched as a compatibility view.

YAGNI: no migration from Idea, no audio fields on Project yet, no
per-track automation curves. Add them only when a real need appears.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NAME_MAX = 64
TYPE_MAX = 32
CONTENT_MAX = 65536
TIMING_MAX = 64
INSTRUMENT_MAX = 64
EFFECT_MAX = 64
EFFECTS_MAX = 32
TEMPO_MIN = 20.0
TEMPO_MAX = 300.0
VOLUME_MIN = 0.0
VOLUME_MAX = 2.0
PAN_MIN = -1.0
PAN_MAX = 1.0
TIME_SIG_DEFAULT = "4/4"
KEY_DEFAULT = "C"


class ProjectError(ValueError):
    """Raised when a Project or Track field fails validation."""


def _validate_str(value, field_name, max_len, allow_empty=False):
    if not isinstance(value, str):
        raise ProjectError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    trimmed = value.strip()
    if not allow_empty and not trimmed:
        raise ProjectError(f"{field_name} must not be empty")
    if len(trimmed) > max_len:
        raise ProjectError(
            f"{field_name} must be <= {max_len} chars, got {len(trimmed)}"
        )
    return trimmed


def _validate_float(value, field_name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectError(
            f"{field_name} must be a number, got {type(value).__name__}"
        )
    f = float(value)
    if not (lo <= f <= hi):
        raise ProjectError(
            f"{field_name} out of range [{lo}-{hi}]: {f}"
        )
    return f


def _validate_time_signature(value):
    if not isinstance(value, str):
        raise ProjectError(
            f"time_signature must be a string, got {type(value).__name__}"
        )
    trimmed = value.strip()
    parts = trimmed.split("/")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ProjectError(
            f"time_signature must look like 'N/M' with integers, got {value!r}"
        )
    num, den = int(parts[0]), int(parts[1])
    if num <= 0 or den <= 0:
        raise ProjectError(
            f"time_signature numerator and denominator must be > 0, got {value!r}"
        )
    return f"{num}/{den}"


@dataclass(frozen=True)
class Track:
    """One musical track inside a Project.

    `type` is a free-form label describing the kind of content
    (e.g. "midi", "pattern", "voice", "audio"). `instrument` optionally
    references an Instrument name from the user's library. `content`
    is an opaque serialized string -- Project never inspects it.
    """

    name: str
    type: str
    instrument: str = ""
    content: str = ""
    timing: str = ""
    volume: float = 1.0
    pan: float = 0.0
    effects: list[str] = field(default_factory=list)

    def __post_init__(self):
        object.__setattr__(
            self, "name", _validate_str(self.name, "track.name", NAME_MAX)
        )
        object.__setattr__(
            self, "type", _validate_str(self.type, "track.type", TYPE_MAX)
        )
        object.__setattr__(
            self, "instrument",
            _validate_str(self.instrument, "track.instrument",
                          INSTRUMENT_MAX, allow_empty=True),
        )
        if not isinstance(self.content, str):
            raise ProjectError(
                f"track.content must be a string, got {type(self.content).__name__}"
            )
        if len(self.content) > CONTENT_MAX:
            raise ProjectError(
                f"track.content must be <= {CONTENT_MAX} chars, "
                f"got {len(self.content)}"
            )
        object.__setattr__(
            self, "timing",
            _validate_str(self.timing, "track.timing",
                          TIMING_MAX, allow_empty=True),
        )
        object.__setattr__(
            self, "volume",
            _validate_float(self.volume, "track.volume", VOLUME_MIN, VOLUME_MAX),
        )
        object.__setattr__(
            self, "pan",
            _validate_float(self.pan, "track.pan", PAN_MIN, PAN_MAX),
        )
        if not isinstance(self.effects, list):
            raise ProjectError(
                f"track.effects must be a list, got {type(self.effects).__name__}"
            )
        if len(self.effects) > EFFECTS_MAX:
            raise ProjectError(
                f"track.effects must have <= {EFFECTS_MAX} entries, "
                f"got {len(self.effects)}"
            )
        cleaned = []
        for e in self.effects:
            cleaned.append(_validate_str(e, "track.effects[]", EFFECT_MAX))
        object.__setattr__(self, "effects", cleaned)

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "instrument": self.instrument,
            "content": self.content,
            "timing": self.timing,
            "volume": self.volume,
            "pan": self.pan,
            "effects": list(self.effects),
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ProjectError(
                f"track entry must be a dict, got {type(data).__name__}"
            )
        missing = {"name", "type"} - data.keys()
        if missing:
            raise ProjectError(
                f"track entry missing fields: {', '.join(sorted(missing))}"
            )
        return cls(
            name=data["name"],
            type=data["type"],
            instrument=data.get("instrument", ""),
            content=data.get("content", ""),
            timing=data.get("timing", ""),
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            effects=list(data.get("effects", [])),
        )


@dataclass(frozen=True)
class Project:
    """A musical project: metadata plus a list of Tracks."""

    name: str
    tracks: list[Track] = field(default_factory=list)
    tempo: float = 120.0
    time_signature: str = TIME_SIG_DEFAULT
    key: str = KEY_DEFAULT
    created: str = ""
    modified: str = ""

    def __post_init__(self):
        object.__setattr__(
            self, "name", _validate_str(self.name, "project.name", NAME_MAX)
        )
        if not isinstance(self.tracks, list):
            raise ProjectError(
                f"project.tracks must be a list, got {type(self.tracks).__name__}"
            )
        for t in self.tracks:
            if not isinstance(t, Track):
                raise ProjectError(
                    f"project.tracks entries must be Track, "
                    f"got {type(t).__name__}"
                )
        object.__setattr__(
            self, "tempo",
            _validate_float(self.tempo, "project.tempo", TEMPO_MIN, TEMPO_MAX),
        )
        object.__setattr__(
            self, "time_signature",
            _validate_time_signature(self.time_signature),
        )
        object.__setattr__(
            self, "key", _validate_str(self.key, "project.key", NAME_MAX)
        )
        if not isinstance(self.created, str):
            raise ProjectError(
                f"project.created must be a string, got {type(self.created).__name__}"
            )
        if not isinstance(self.modified, str):
            raise ProjectError(
                f"project.modified must be a string, got {type(self.modified).__name__}"
            )

    def to_dict(self):
        return {
            "name": self.name,
            "tracks": [t.to_dict() for t in self.tracks],
            "tempo": self.tempo,
            "time_signature": self.time_signature,
            "key": self.key,
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ProjectError(
                f"project entry must be a dict, got {type(data).__name__}"
            )
        missing = {"name"} - data.keys()
        if missing:
            raise ProjectError(
                f"project entry missing fields: {', '.join(sorted(missing))}"
            )
        return cls(
            name=data["name"],
            tracks=[Track.from_dict(t) for t in data.get("tracks", [])],
            tempo=data.get("tempo", 120.0),
            time_signature=data.get("time_signature", TIME_SIG_DEFAULT),
            key=data.get("key", KEY_DEFAULT),
            created=data.get("created", ""),
            modified=data.get("modified", ""),
        )


__all__ = ["Project", "ProjectError", "Track"]
