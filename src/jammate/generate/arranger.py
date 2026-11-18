"""Turn the jam state into concrete notes, one bar at a time."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict

from jammate.generate.harmony import progression
from jammate.generate.patterns import bass_bar, comp_bar, drum_bar
from jammate.generate.rhythm import free_rhythm_parts, rhythm_parts
from jammate.music import BEATS_PER_BAR, Chord, Note
from jammate.render.free_rhythm_midi import free_rhythm_ticks
from jammate.rhythm import FreeRhythm
from jammate.state import JamState

PHRASE_BARS = 4


def chord_for_bar(state: JamState, bar_index: int) -> Chord:
    loop = progression(state.key, state.progression_variant)
    return loop[bar_index % len(loop)]


def arrange_bar(state: JamState, bar_index: int, lead: tuple[Note, ...] = (), *,
                end_bar: int | None = None) -> tuple[Note, ...]:
    """All parts for one bar in absolute beats. `lead` is bar-relative."""
    if not state.playing:
        return ()
    chord = chord_for_bar(state, bar_index)
    phrase_pos = bar_index % PHRASE_BARS
    if isinstance(state.rhythm, FreeRhythm):
        backing = _free_backing(state.rhythm, state, chord, bar_index, end_bar)
    elif state.rhythm is not None:
        backing = rhythm_parts(chord, state.rhythm, state.rhythm_mode, state.energy, bar_index)
    else:
        backing = (drum_bar(state.energy, phrase_pos)
                   + bass_bar(chord, state.energy)
                   + comp_bar(chord, state.energy))
    bar_notes = backing + tuple(lead)
    offset = bar_index * BEATS_PER_BAR
    return tuple(n.shifted(offset) for n in bar_notes)


def _free_backing(rhythm, state, chord, bar_index, end_bar):
    elapsed = bar_index - (rhythm.start_bar or 0)
    if elapsed < 0:
        return ()
    period = rhythm.required_bars(state.tempo_bpm)
    phrase_bar = elapsed % period
    phrase_start = bar_index - phrase_bar
    duration_s = rhythm.audio_duration_s
    if end_bar is not None:
        duration_s = min(duration_s, (end_bar - phrase_start) * BEATS_PER_BAR * 60 / state.tempo_bpm)

    # Resolve the whole rendered phrase before picking this bar's slice. A
    # final hit can move across a bar line by a MIDI tick, and the preceding
    # note's release must use the same adjusted hit. Source evidence stays put.
    onsets = rhythm.onset_seconds[:bisect_left(rhythm.onset_seconds, duration_s)]
    ticks, _, tick_rate = free_rhythm_ticks(onsets, duration_s, state.tempo_bpm)
    beats = tuple((second if round(second * tick_rate) == tick else tick / tick_rate) * state.tempo_bpm / 60
                  for second, tick in zip(onsets, ticks))
    beat_start = phrase_bar * BEATS_PER_BAR
    first = bisect_left(beats, beat_start)
    stop = bisect_left(beats, beat_start + BEATS_PER_BAR, lo=first)
    hits = tuple((beat - beat_start, accent) for beat, accent in
                 zip(beats[first:stop], rhythm.accents[first:stop]))
    # A hit before a bar line may ring across it. Release by the next hit,
    # end of the capture, or end of the whole render, whichever comes first.
    phrase_end = duration_s * state.tempo_bpm / 60
    next_hit_or_end = beats[stop] if stop < len(beats) else phrase_end
    end_beat = next_hit_or_end - beat_start
    return free_rhythm_parts(chord, hits, state.rhythm_mode, state.energy, bar_index, end_beat)


def place_lead(motif: tuple[Note, ...], start_bar: int) -> dict[int, tuple[Note, ...]]:
    """Split a motif (beat 0 = its first downbeat) into bar-relative chunks."""
    bars: dict[int, list[Note]] = defaultdict(list)
    for note in motif:
        bar_offset = int(note.start // BEATS_PER_BAR)
        bars[start_bar + bar_offset].append(note.shifted(-bar_offset * BEATS_PER_BAR))
    return {bar: tuple(notes) for bar, notes in sorted(bars.items())}
