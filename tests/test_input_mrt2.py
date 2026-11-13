"""Real orchestration/renderer boundaries; only model audio is a labelled double."""
import base64
import copy
import io
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from jammate.contracts import InputEvent
from jammate.contracts.adapters import from_text
from jammate.input_band import render_clip
from jammate.render.capabilities import BackendCapabilityError

ROOT = Path(__file__).resolve().parents[1]


def fixture(kind):
    return json.loads((ROOT / 'examples/input_events' / f'{kind}.json').read_text(encoding='utf-8'))


def model_double(prompt, *, output, duration, **kwargs):
    time = np.arange(round(duration * 48000)) / 48000
    samples = .05 * np.sin(2 * np.pi * 220 * time)
    sf.write(output, np.column_stack((samples, samples)), 48000, subtype='PCM_16')
    return {'inference': 'injected_test_double'}


@pytest.mark.parametrize('kind', ['humming', 'rhythm', 'text'])
def test_inputs_reach_shared_mrt2_runtime_with_exact_event_and_uncommitted_preview(monkeypatch, kind):
    import renderer_experiments.app.mrt2 as renderer
    monkeypatch.setattr(renderer, 'generate', model_double)
    event = (from_text('  来一段，慢一点\n', session_id='text-preview').to_dict()
             if kind == 'text' else fixture(kind))
    original = copy.deepcopy(event)
    result = render_clip(event, creative=True, backend='mrt2', allow_preview=True)
    assert result['input_event'] == original == event
    InputEvent.from_dict(result['input_event'])
    assert result['plan']['trigger_event_ids'] == [event['event_id']]
    assert result['receipt']['inference'] == 'injected_test_double'
    assert result['receipt']['phase'] == 'preview'
    assert result['receipt']['state_committed'] is False
    assert result['state_after'] == result['state_before']
    assert result['plan']['based_on_state_version'] == result['state_before']['state_version']
    wave, sr = sf.read(io.BytesIO(base64.b64decode(result['wav'])))
    assert sr == 48000 and np.max(np.abs(wave)) > .01


@pytest.mark.parametrize('kind', ['humming', 'rhythm'])
def test_strict_mrt2_rejects_audio_inputs_before_model_loading(kind):
    with pytest.raises(BackendCapabilityError):
        render_clip(fixture(kind), backend='mrt2')


def test_rhythm_demo_controls_reach_plan_without_changing_perception():
    event = fixture('rhythm')
    result = render_clip(event, mode='simplify', energy=0, bars=2)
    assert result['input_event'] == event
    assert result['bars'] == result['plan']['valid_for_bars'] == 2
    assert result['state_before']['rhythm_mode'] == 'simplify'
    assert result['state_before']['feel']['energy'] == 0
    assert result['plan']['strategy'] == 'RESPOND'


def test_low_confidence_rhythm_does_not_generate_unrelated_music():
    event = fixture('rhythm')
    event['payload']['rhythm']['confidence'] = .1
    with pytest.raises(ValueError, match='拍点不足'):
        render_clip(event, backend='mrt2', allow_preview=True)


@pytest.mark.parametrize('changes', [{'energy': True}, {'bars': 0}, {'backend': 'unknown'}, {'allow_preview': 'yes'}])
def test_invalid_render_settings_rejected(changes):
    with pytest.raises(ValueError):
        render_clip(fixture('rhythm'), **changes)
