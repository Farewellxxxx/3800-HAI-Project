import base64
import io
from pathlib import Path

import mido
import numpy as np
import pretty_midi
import pytest
import soundfile as sf
import librosa
from scipy.signal import butter, sosfilt

from jammate.analysis.free_rhythm import analyze_free_rhythm
from jammate.analysis import rhythm as original_rhythm
from jammate.contracts import InputEvent
from jammate.contracts.adapters import from_free_rhythm, from_text
from jammate.contracts.input_event import InputEventError
from jammate.interaction import TransportPosition
from jammate.orchestration.agent import RuleAgent
from jammate.orchestration.manager import StateManager
from jammate.orchestration.offline import prepare_plan
from jammate.reference_bridge import ReferenceBridge, ReferenceFailure
from jammate.state import JamState
from renderer_experiments.app.band_plan import KevinRuntime
from renderer_experiments.app.mrt2 import MRT2Runtime


ROOT = Path(__file__).resolve().parents[1]
SR = 24000


def upstream_result(audio, sample_rate):
    """Reference the unchanged recognizer, with its historical mono conversion."""
    mono = np.asarray(audio, dtype=np.float32)
    if mono.ndim == 2:
        mono = np.mean(mono, axis=1)
    times, accents = original_rhythm._onsets_and_accents(mono, sample_rate)
    unique = sorted(set(times.tolist()))
    return unique, [float(np.max(accents[times == when])) for when in unique]


def test_upstream_fidelity_preserves_original_backtracking_and_peak_accents():
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(6.5, [(.113, .9), (.202, .12), (.863, .55), (5.861, .4)], noise=.002))))
    expected = upstream_result(audio, sr)
    assert expected[0][-1] > 5
    assert analyze_free_rhythm(audio, sr) == expected


def test_upstream_fidelity_keeps_original_whole_clip_guard():
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(.7, [(.3, .009)]))))
    assert analyze_free_rhythm(audio, sr) == ([], [])


def test_upstream_fidelity_keeps_global_gate_even_when_it_misses_a_soft_hit():
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(1.4, [(.25, .8), (.84, .035)]))))
    expected = upstream_result(audio, sr)
    assert len(expected[0]) == 1  # The original 12% gate discards the weak hit.
    assert analyze_free_rhythm(audio, sr) == expected


def test_upstream_fidelity_passes_original_librosa_arguments_and_60ms_peak_strength(monkeypatch):
    audio = np.zeros(2 * SR, dtype=np.float32)
    audio[round(.25 * SR)] = .4
    audio[round(.30 * SR)] = .8  # Within the first onset's 60 ms strength window.
    audio[round(1.05 * SR)] = .6

    def recognize(**kwargs):
        assert set(kwargs) == {"y", "sr", "hop_length", "units", "backtrack"}
        assert kwargs["sr"] == SR
        assert kwargs["hop_length"] == 256
        assert kwargs["units"] == "time" and kwargs["backtrack"] is True
        np.testing.assert_array_equal(kwargs["y"], np.pad(audio, (2400, 2400)))
        return np.array([.35, 1.15])

    monkeypatch.setattr(librosa.onset, "onset_detect", recognize)
    times, accents = analyze_free_rhythm(audio, SR)
    assert times == [.35 - .1, 1.15 - .1]
    assert accents == [1., float(np.float32(.6) / np.float32(.8))]


def test_upstream_fidelity_only_consolidates_exact_times(monkeypatch):
    # A dependency double isolates representation, not acoustic detection.
    # .25 and .25000000001 are deliberately distinct, with no epsilon merge.
    def recognize(mono, sample_rate):
        assert mono.dtype == np.float32
        assert mono.ndim == 1
        assert sample_rate == SR
        return np.array([0., .25, .25, .25000000001, 5.731]), np.array([.2, .3, .8, .4, 1.])

    monkeypatch.setattr(original_rhythm, "_onsets_and_accents", recognize)
    result = analyze_free_rhythm(np.zeros((6 * SR, 2)), SR)
    assert result == ([0., .25, .25000000001, 5.731], [.2, .8, .4, 1.])
    assert all(type(value) is float for group in result for value in group)


@pytest.mark.parametrize("layout", ["mono", "same", "opposite", "one_silent"])
def test_upstream_fidelity_uses_historical_float32_mono_mean(layout):
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(.7, [(.3, .5)]))))
    if layout != "mono":
        second = audio if layout == "same" else -audio if layout == "opposite" else np.zeros_like(audio)
        audio = np.column_stack((audio, second))
    assert analyze_free_rhythm(audio, sr) == upstream_result(audio, sr)


def test_free_rhythm_has_no_hits_without_librosa_candidates(monkeypatch):
    # Removing library candidates must disable every hit, including edge hits:
    # a second independent detector would silently violate the backbone contract.
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(.7, [(0, .5), (.3, .8)]))))
    assert len(analyze_free_rhythm(audio, sr)[0]) == 2
    monkeypatch.setattr(librosa.onset, "onset_detect", lambda **kwargs: np.array([], dtype=int))
    assert analyze_free_rhythm(audio, sr) == ([], [])


def test_gain_scaled_soft_attacks_match_upstream_including_misses():
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(1.4, [(.25, .8), (.84, .035)]))))
    assert analyze_free_rhythm(audio * .1, sr) == upstream_result(audio * .1, sr)


@pytest.mark.parametrize("kind", ["rumble", "gated_tone"])
def test_sustained_background_matches_upstream_including_false_onsets(kind):
    t = np.arange(round(2.1 * SR)) / SR
    if kind == "rumble":
        audio = .055 * np.sin(2 * np.pi * 43 * t) + .025 * np.sin(2 * np.pi * 81 * t)
    else:
        audio = .08 * np.sin(2 * np.pi * 220 * t) * ((t >= .4) & (t < 1.7))
    assert analyze_free_rhythm(audio, SR) == upstream_result(audio, SR)


def test_close_double_and_clipped_final_hit_match_upstream():
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(.7, [(.11, .06), (.168, .8), (.693, .4)]))))
    assert analyze_free_rhythm(audio, sr) == upstream_result(audio, sr)


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    with ReferenceBridge(ROOT, scratch=tmp_path_factory.mktemp("free-rhythm"), implementation="workspace") as worker:
        yield worker


def make_wave(duration, hits=(), noise=0, *, sample_rate=SR, seed=417):
    rng = np.random.default_rng(seed)
    audio = rng.normal(0, noise, int(sample_rate * duration))
    for when, strength in hits:
        start = round(when * sample_rate)
        t = np.arange(min(round(.038 * sample_rate), len(audio) - start)) / sample_rate
        audio[start:start + len(t)] += strength * rng.uniform(-1, 1, len(t)) * np.exp(-t * 115)
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def analyze(bridge, duration, hits=(), *, started_at=2.5, noise=0):
    return bridge.request("rhythm/analyze", {"wav": make_wave(duration, hits, noise),
                           "session_id": "test_free_rhythm", "started_at": started_at})


def test_irregular_phrase_preserves_upstream_results_through_event_and_midi(bridge):
    hits = [(.113, .9), (.202, .12), (.863, .55), (2.319, .45), (4.151, .8), (5.861, .4)]
    result = analyze(bridge, 6.5, hits, noise=.002)
    assert result["schema_version"] == "1.3.0"
    assert result["confidence"] is None
    assert (result["started_at"], result["ended_at"]) == (2.5, 9)
    payload = result["payload"]
    assert payload["audio_duration_s"] == 6.5
    assert payload["status"] == "ready"
    assert payload["rhythm"] == payload["raw_rhythm"]
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(6.5, hits, noise=.002))))
    times, accents = upstream_result(audio, sr)
    assert payload["rhythm"] == {"onset_seconds": times, "accents": accents}
    assert times[-1] > 5  # No one-bar crop or forced grid in the free adapter.
    assert InputEvent.from_dict(result).to_dict() == result
    rendered = bridge.request("rhythm/midi", {"event": result})
    midi = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(rendered["midi"])))
    notes = midi.instruments[0].notes
    assert [note.start for note in notes] == pytest.approx(times, abs=.0001)
    assert [note.velocity for note in notes] == [max(1, round(value * 127)) for value in accents]


@pytest.mark.parametrize("noise", [0, .012])
def test_silence_and_stationary_noise_keep_upstream_status(bridge, noise):
    result = analyze(bridge, .7, started_at=None, noise=noise)
    assert result["started_at"] is result["ended_at"] is None
    audio, sr = sf.read(io.BytesIO(base64.b64decode(make_wave(.7, noise=noise))))
    times, accents = upstream_result(audio, sr)
    assert result["payload"]["status"] == ("ready" if times else "no_onsets")
    assert result["payload"]["rhythm"] == {"onset_seconds": times, "accents": accents}


def test_a_single_hit_at_recording_start_has_no_count_in(bridge):
    result = analyze(bridge, .53, [(0, .38)])
    assert result["payload"]["rhythm"]["onset_seconds"] == pytest.approx([0], abs=.012)


def test_noise_at_recording_edge_matches_upstream_at_8_khz(bridge):
    wav = make_wave(.5, noise=.012, sample_rate=8000, seed=3)
    result = bridge.request("rhythm/analyze", {"wav": wav,
                                               "session_id": "edge_noise", "started_at": None})
    audio, sr = sf.read(io.BytesIO(base64.b64decode(wav)))
    times, accents = upstream_result(audio, sr)
    assert result["payload"]["rhythm"] == {"onset_seconds": times, "accents": accents}


def room_noise(t, rng):
    # Uneven room and voiced sound; no percussion or discontinuities.
    pitch = 85 + 45 * np.sin(2 * np.pi * .84 * t)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    voiced = .045 * np.sin(phase) ** 7 + .008 * np.sin(2 * phase + .4)
    swell = np.clip(.3 + .7 * np.sin(2 * np.pi * 1.7 * t + .6), 0, 1)
    body = sosfilt(butter(2, [80, 400], fs=SR, btype="bandpass", output="sos"),
                   rng.normal(0, 1, len(t)))
    return .0015 * rng.normal(0, 1, len(t)) + .005 * np.sin(2 * np.pi * 50 * t) + swell * (voiced + .016 * body)


def test_modulated_room_sound_keeps_upstream_false_onsets():
    rng = np.random.default_rng(11)
    t = np.arange(round(7.14 * SR)) / SR
    audio = room_noise(t, rng)
    assert analyze_free_rhythm(audio, SR) == upstream_result(audio, SR)


def test_ringing_claps_and_soft_double_match_upstream_including_misses():
    rng = np.random.default_rng(11)
    t = np.arange(round(4.1 * SR)) / SR
    audio = room_noise(t, rng)
    duration = round(.42 * SR)
    decay_t = t[:duration]
    reverberation = butter(2, [350, 2800], fs=SR, btype="bandpass", output="sos")
    for when, strength in [(1.17, .8), (1.228, .14), (2.95, .4), (3.487, .045)]:
        clap = rng.uniform(-1, 1, duration) * np.exp(-decay_t / .008)
        clap += .12 * sosfilt(reverberation, rng.normal(0, 1, duration)) * np.exp(-decay_t / .064)
        clap += .1 * (np.cos(2 * np.pi * 48 * decay_t) + np.cos(2 * np.pi * 93 * decay_t)) * np.exp(-decay_t / .071)
        start = round(when * SR)
        audio[start:start + duration] += strength * clap
    assert analyze_free_rhythm(audio, SR) == upstream_result(audio, SR)


@pytest.mark.parametrize("sample_rate, frequency", [(8_000, 60), (24_000, 100), (48_000, 180)])
def test_low_pitched_taps_match_upstream_at_each_sample_rate(sample_rate, frequency):
    rng = np.random.default_rng(84)
    t = np.arange(round(1.4 * sample_rate)) / sample_rate
    audio = .002 * rng.normal(0, 1, len(t)) + .004 * np.sin(2 * np.pi * 50 * t)
    ring_t = t[:round(.4 * sample_rate)]
    ring = np.sin(2 * np.pi * frequency * ring_t) * np.exp(-ring_t / .042)
    for when, strength in [(.25, .24), (.84, .035)]:
        start = round(when * sample_rate)
        audio[start:start + len(ring)] += strength * ring
    assert analyze_free_rhythm(audio, sample_rate) == upstream_result(audio, sample_rate)


def test_validated_edits_keep_evidence_and_drive_pure_midi(bridge):
    event = analyze(bridge, 6.5, [(.25, .8), (1.13, .38), (4.372, .62)])
    raw = event["payload"]["raw_rhythm"]
    event["event_id"] = "edited_free_rhythm"
    event["payload"]["rhythm"] = {"onset_seconds": [.137, 1.257, 4.875], "accents": [.3, 1., .66]}
    assert InputEvent.from_dict(event).payload["raw_rhythm"] == raw
    result = bridge.request("rhythm/midi", {"event": event})
    midi_bytes = base64.b64decode(result["midi"])
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    assert len(midi.instruments) == 1
    track = midi.instruments[0]
    assert track.is_drum
    assert [note.pitch for note in track.notes] == [36, 36, 36]
    assert [note.start for note in track.notes] == pytest.approx([.137, 1.257, 4.875], abs=.0001)
    assert [note.velocity for note in track.notes] == [38, 127, 84]
    assert [hit["velocity"] for hit in result["hits"]] == [note.velocity for note in track.notes]
    assert [hit["onset_s"] for hit in result["hits"]] == pytest.approx([note.start for note in track.notes])
    assert [hit["duration_s"] for hit in result["hits"]] == pytest.approx([note.end - note.start for note in track.notes])
    assert result["duration_s"] == 6.5
    assert mido.MidiFile(file=io.BytesIO(midi_bytes)).length == pytest.approx(6.5, abs=.0001)

    event["payload"]["rhythm"] = {"onset_seconds": [], "accents": []}
    with pytest.raises(InputEventError, match="status"):
        InputEvent.from_dict(event)
    event["payload"]["status"] = "no_onsets"
    assert InputEvent.from_dict(event).payload["raw_rhythm"] == raw
    silence = bridge.request("rhythm/midi", {"event": event})
    assert silence["hits"] == []
    assert mido.MidiFile(file=io.BytesIO(base64.b64decode(silence["midi"]))).length == pytest.approx(6.5)


@pytest.mark.parametrize("onsets,accents", [([.1, .2], [1]), ([.2, .1], [1, 1]), ([.1, .1], [1, 1]), ([.7], [1]), ([.1], [0])])
def test_free_event_validates_order_range_and_accents(bridge, onsets, accents):
    event = analyze(bridge, .7)
    for name, status in [("raw_rhythm", "no_onsets"), ("rhythm", "ready")]:
        invalid = {**event, "payload": {**event["payload"], "status": status,
                   name: {"onset_seconds": onsets, "accents": accents}}}
        with pytest.raises(InputEventError):
            InputEvent.from_dict(invalid)


def test_free_event_cannot_masquerade_as_legacy_schema(bridge):
    event = analyze(bridge, .63, [(.12, 1)])
    with pytest.raises(InputEventError, match="payload"):
        InputEvent.from_dict({**event, "schema_version": "1.2.0"})


def test_shared_band_renders_edited_phrase_beyond_eight_bars(bridge):
    event = analyze(bridge, 20.5, [(.177, .8), (2.613, .9), (19.85, .4)])
    edited = [.253, 2.633, 18.777]
    event["event_id"] = "free_long_edited"
    event["payload"]["rhythm"] = {"onset_seconds": edited, "accents": [.84, .66, .48]}
    result = bridge.request("input/render", {"event": event, "mode": "follow", "bars": 8})
    assert result["input_event"] == event
    assert result["bars"] == result["plan"]["valid_for_bars"] == 11
    assert result["tempo_source"] == "arrangement_default"
    assert result["tempo_bpm"] == 120
    assert result["plan"]["trigger_event_ids"] == [event["event_id"]]
    assert result["plan"]["actions"][0]["parameters"]["rhythm_event_id"] == event["event_id"]
    state = JamState.from_dict(result["state_after"])
    assert list(state.rhythm.onset_seconds) == edited
    midi = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result["midi"])))
    drums = next(track for track in midi.instruments if track.is_drum)
    assert sorted({round(note.start, 3) for note in drums.notes}) == pytest.approx(edited, abs=.002)
    with sf.SoundFile(io.BytesIO(base64.b64decode(result["wav"]))) as wav:
        assert len(wav) / wav.samplerate >= 22


def test_free_rhythm_adoption_at_nonzero_bar_preserves_session_tempo_and_rests(bridge):
    event = analyze(bridge, 5.0, [(.333, .4), (3.19, .85)])
    manager = StateManager(JamState(session_id=event["session_id"], tempo_bpm=96,
                                  position=TransportPosition(bar=4, next_bar=5)))
    accepted = manager.ingest([InputEvent.from_dict(event)])
    state, history = manager.decision_snapshot()
    plan = RuleAgent().decide(accepted, state, history=history)
    result = prepare_plan(state, plan)
    seconds = sorted({(note.start - 20) * 60 / result.tempo_bpm for note in result.notes if note.instrument == "drums"})
    assert result.tempo_bpm == state.tempo_bpm == 96
    assert seconds == pytest.approx(event["payload"]["rhythm"]["onset_seconds"], abs=1e-6)


def test_shared_band_requires_selected_hits(bridge):
    event = analyze(bridge, .7)
    with pytest.raises(ReferenceFailure):
        bridge.request("input/render", {"event": event})


@pytest.mark.parametrize("duration", [2.3, 2.0])
def test_free_band_preserves_hit_just_before_bar_boundary(bridge, tmp_path, duration):
    event = from_free_rhythm([1.9998], [.8], audio_duration_s=duration, session_id="near_boundary")
    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=120))
    accepted = manager.ingest([event])
    plan = RuleAgent().decide(accepted, manager.state)
    kevin = KevinRuntime(tmp_path, executable=Path("."), soundfont=Path("."))
    mrt2 = MRT2Runtime(tmp_path, allow_preview=True)
    for runtime in (kevin, mrt2):
        performance = runtime.validate(manager.state, plan)
        assert {note.start * .5 for note in performance.notes if note.instrument == "drums"} == {1.9998}
        assert all(note.end * .5 <= duration for note in performance.notes)
        if duration > 2.0:
            assert all(note.end * .5 > 2.0 for note in performance.notes)

    result = bridge.request("input/render", {"event": event.to_dict(), "mode": "follow"})
    score = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result["midi"])))
    drum_notes = next(track.notes for track in score.instruments if track.is_drum)
    assert len(drum_notes) == 2
    assert [note.start for note in drum_notes] == pytest.approx([1.9998, 1.9998], abs=.00003)


def test_subsequent_build_repeats_whole_free_phrase_instead_of_a_bar():
    event = from_free_rhythm([.35, 2.11, 5.1], [.8, .4, 1], audio_duration_s=5.5, session_id="loop_free")
    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=120))
    agent = RuleAgent()
    first = agent.decide(manager.ingest([event]), manager.state)
    assert first.to_dict()["valid_for_bars"] == 3
    manager.stage(first)
    assert manager.acknowledge(first, succeeded=True, effective_bar=0, completed_bar=3)
    second = agent.decide(manager.ingest([from_text("build", session_id=event.session_id)]), manager.state)
    performance = prepare_plan(manager.state, second)
    assert performance.start_bar == 3
    drum_times = sorted({(note.start - 12) * .5 for note in performance.notes if note.instrument == "drums"})
    assert drum_times == pytest.approx([.35, 2.11, 5.1, 6.35])
    assert manager.state.rhythm.audio_duration_s == 5.5


@pytest.mark.parametrize("times,duration", [([1.876, 29.999999], 30), ([.5], .50001)])
def test_free_band_final_hit_has_same_start_tick_as_standalone(bridge, tmp_path, times, duration):
    event = from_free_rhythm(times, [.8] * len(times), audio_duration_s=duration, session_id="last_tick")
    document = event.to_dict()
    direct = bridge.request("rhythm/midi", {"event": document})
    result = bridge.request("input/render", {"event": document, "mode": "follow"})
    assert result["input_event"] == document
    band = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result["midi"])))
    drums = next(track.notes for track in band.instruments if track.is_drum)
    assert sorted({note.start for note in drums}) == pytest.approx([hit["onset_s"] for hit in direct["hits"]], abs=1e-8)
    assert drums[-1].end > drums[-1].start

    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=120))
    plan = RuleAgent().decide(manager.ingest([event]), manager.state)
    for runtime in (KevinRuntime(tmp_path, executable=Path("."), soundfont=Path(".")),
                    MRT2Runtime(tmp_path, allow_preview=True)):
        performance = runtime.validate(manager.state, plan)
        assert sorted({note.start * .5 for note in performance.notes if note.instrument == "drums"}) == pytest.approx(
            [hit["onset_s"] for hit in direct["hits"]])


def test_free_band_midi_ends_at_plan_end_even_with_a_long_trailing_rest(bridge):
    event = from_free_rhythm([.5], [.8], audio_duration_s=29.85, session_id="long_rest")
    result = bridge.request("input/render", {"event": event.to_dict(), "mode": "follow"})
    assert result["bars"] == 15
    score = mido.MidiFile(file=io.BytesIO(base64.b64decode(result["midi"])))
    assert score.length == pytest.approx(30, abs=1e-7)


@pytest.mark.parametrize("final_hit,duration", [(2.0, 2.000001), (2.0000005, 2.000001), (2.0, 2 + 1 / 96000)])
def test_free_band_releases_previous_hit_before_shifted_final_attack(bridge, tmp_path, final_hit, duration):
    event = from_free_rhythm([1.95, final_hit], [.8, .8], audio_duration_s=duration, session_id="shifted_final_attack")
    document = event.to_dict()
    direct = bridge.request("rhythm/midi", {"event": document})
    result = bridge.request("input/render", {"event": document, "mode": "follow"})
    assert result["input_event"] == document
    score = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result["midi"])))
    drums = next(track.notes for track in score.instruments if track.is_drum)
    first, final = [hit["onset_s"] for hit in direct["hits"]]
    assert sorted({note.start for note in drums}) == pytest.approx([first, final], abs=1e-9)
    assert max(note.end for note in drums if abs(note.start - first) < 1e-9) == pytest.approx(final, abs=1e-9)

    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=120))
    plan = RuleAgent().decide(manager.ingest([event]), manager.state)
    for runtime in (KevinRuntime(tmp_path, executable=Path("."), soundfont=Path(".")),
                    MRT2Runtime(tmp_path, allow_preview=True)):
        performance = runtime.validate(manager.state, plan)
        assert sorted({note.start * .5 for note in performance.notes if note.instrument == "drums"}) == pytest.approx(
            [first, final], abs=1e-9)


def test_free_midi_and_every_band_renderer_reject_colliding_hit_ticks(bridge):
    event = from_free_rhythm([1.25, 1.250001], [.8, .4], audio_duration_s=2, session_id="tick_collision")
    with pytest.raises(ReferenceFailure) as direct:
        bridge.request("rhythm/midi", {"event": event.to_dict()})
    for backend in ("default", "fluidsynth", "mrt2"):
        with pytest.raises(ReferenceFailure) as arranged:
            bridge.request("input/render", {"event": event.to_dict(), "renderer": backend, "allow_preview": True})
        assert str(arranged.value) == str(direct.value)
