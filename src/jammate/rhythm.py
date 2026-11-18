"""Validated one-bar rhythm exchanged by input, director and generator.

Only 4/4 is supported. ``beat_origin_s`` belongs to the input audio clock;
it is not a request to restart an already playing band. Live updates take
effect at the next unrendered bar on the output clock.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from jammate.music import BEATS_PER_BAR


class RhythmMode(str, Enum):
    FOLLOW = "follow"
    VARY = "vary"
    SIMPLIFY = "simplify"


@dataclass(frozen=True)
class RhythmContext:
    tempo_bpm: float
    onset_beats: tuple[float, ...]
    accents: tuple[float, ...]
    beat_origin_s: float = 0.0
    beats_per_bar: int = BEATS_PER_BAR
    confidence: float = 1.0

    def __post_init__(self) -> None:
        # Accept JSON lists but keep the shared state immutable.
        object.__setattr__(self, "onset_beats", tuple(self.onset_beats))
        object.__setattr__(self, "accents", tuple(self.accents))
        if not math.isfinite(self.tempo_bpm) or not 60 <= self.tempo_bpm <= 180:
            raise ValueError("rhythm tempo_bpm must be finite and within 60-180")
        if not math.isfinite(self.beat_origin_s) or self.beat_origin_s < 0:
            raise ValueError("beat_origin_s must be finite and nonnegative")
        if self.beats_per_bar != BEATS_PER_BAR:
            raise ValueError("only 4/4 rhythms (beats_per_bar=4) are supported")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be within 0-1")
        if len(self.onset_beats) != len(self.accents):
            raise ValueError("onset_beats and accents must have the same length")
        if len(self.onset_beats) > 16:
            raise ValueError("at most 16 onsets per bar are supported")
        if any(not math.isfinite(b) or not 0 <= b < BEATS_PER_BAR for b in self.onset_beats):
            raise ValueError("onset_beats must be finite and within [0, 4)")
        if any(a >= b for a, b in zip(self.onset_beats, self.onset_beats[1:])):
            raise ValueError("onset_beats must be strictly increasing without duplicates")
        if any(not math.isfinite(a) or not 0 < a <= 1 for a in self.accents):
            raise ValueError("accents must be within (0, 1]")
        # DSP libraries return numpy scalars, which json.dumps cannot always
        # encode. Normalize at the shared interface, including logged events.
        object.__setattr__(self, "tempo_bpm", float(self.tempo_bpm))
        object.__setattr__(self, "beat_origin_s", float(self.beat_origin_s))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "beats_per_bar", int(self.beats_per_bar))
        object.__setattr__(self, "onset_beats", tuple(float(b) for b in self.onset_beats))
        object.__setattr__(self, "accents", tuple(float(a) for a in self.accents))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FreeRhythm:
    """A recording-relative phrase, anchored to a session bar when adopted."""

    onset_seconds: tuple[float, ...]
    accents: tuple[float, ...]
    audio_duration_s: float
    start_bar: int | None = None

    def __post_init__(self) -> None:
        onsets, accents = tuple(self.onset_seconds), tuple(self.accents)
        if not math.isfinite(self.audio_duration_s) or not .5 <= self.audio_duration_s <= 30:
            raise ValueError("free rhythm duration must be within 0.5–30 seconds")
        if self.start_bar is not None and (type(self.start_bar) is not int or self.start_bar < 0):
            raise ValueError("free rhythm start_bar must be a nonnegative integer or null")
        if len(onsets) != len(accents):
            raise ValueError("free rhythm onset and accent lengths differ")
        if any(not math.isfinite(time) or not 0 <= time < self.audio_duration_s for time in onsets):
            raise ValueError("free rhythm onsets must be within the recording")
        if any(a >= b for a, b in zip(onsets, onsets[1:])):
            raise ValueError("free rhythm onsets must be strictly increasing")
        if any(not math.isfinite(accent) or not 0 < accent <= 1 for accent in accents):
            raise ValueError("free rhythm accents must be within (0, 1]")
        object.__setattr__(self, "onset_seconds", onsets)
        object.__setattr__(self, "accents", accents)

    def required_bars(self, tempo_bpm: float) -> int:
        return math.ceil(self.audio_duration_s * tempo_bpm / (60 * BEATS_PER_BAR))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def rhythm_context_from_dict(data: dict) -> RhythmContext | FreeRhythm:
    return FreeRhythm(**data) if "onset_seconds" in data else RhythmContext(**data)


def load_rhythm(path: str | Path) -> RhythmContext:
    """Load the same strict schema used by ``UserRhythm`` events."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("rhythm JSON must contain an object")
        return RhythmContext(**data)
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"invalid rhythm JSON: {exc}") from exc
