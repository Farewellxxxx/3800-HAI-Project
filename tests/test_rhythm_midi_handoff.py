import base64
import io
import json
from pathlib import Path

import pretty_midi
import pytest

from jammate.reference_bridge import ReferenceBridge


ROOT = Path(__file__).resolve().parents[1]


def test_mrt2_rhythm_input_contains_only_the_user_hits(tmp_path):
    event = json.loads((ROOT / "examples/reference-creation/rhythm.input.json").read_text())
    with ReferenceBridge(ROOT, scratch=tmp_path) as bridge:
        result = bridge.request("rhythm/midi", {"event": event})

    score = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result["midi"])))
    assert len(score.instruments) == 1
    track = score.instruments[0]
    assert track.is_drum
    bpm = score.get_tempo_changes()[1][0]
    assert bpm == pytest.approx(100.4464, abs=.001)
    assert [note.start * bpm / 60 for note in track.notes] == pytest.approx([0, 1, 1.5, 3])
    assert result["duration_s"] == pytest.approx(4 * 60 / bpm)
