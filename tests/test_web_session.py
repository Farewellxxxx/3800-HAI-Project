"""Web revisions preserve musical evidence, execute real plans and commit once."""
import base64
import io
import json
from copy import deepcopy
from pathlib import Path
from threading import Event, Thread

import pretty_midi
import pytest

from jammate import input_band

ROOT = Path(__file__).resolve().parents[1]


def draft(*, combined=False, **settings):
    inputs = {'humming': json.loads((ROOT/'examples/web_band/humming.agent.json').read_text())}
    if combined:
        inputs['rhythm'] = json.loads((ROOT/'examples/web_band/rhythm.agent.json').read_text())
    return {'inputs': inputs, 'settings': {'tempo_source': 'manual', 'bpm': 120,
        'key': {'tonic': 2, 'mode': 'major'}, 'melody_origin_s': 0, 'placement_beats': 0,
        'alignment_confirmed': True, **settings}}


def session(data=None, **kwargs):
    assert hasattr(input_band, 'SessionStore'), 'web session service is not implemented'
    store = input_band.SessionStore(**kwargs)
    sid = store.create()['session_id']
    store.update(sid, 1, data or draft())
    return store, sid


def tracks(result):
    midi = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(result['midi'])))
    return {i.name: [(n.pitch, round(n.start, 3), round(n.end-n.start, 3), n.velocity) for n in i.notes]
            for i in midi.instruments}


def test_manual_tempo_key_and_offset_preserve_original_melody():
    data = draft(melody_origin_s=.1, placement_beats=2)
    original = deepcopy(data)
    store, sid = session(data)
    result = store.render(sid, 1, 'r1')
    assert result['tempo_bpm'] == 120
    assert result['state']['harmony']['key'] == {'tonic': 2, 'mode': 'major'}
    lead = tracks(result)['lead']
    for played, source in zip(lead, data['inputs']['humming']['payload']['melody']['notes'], strict=True):
        assert played[0] == source['pitchMidi']
        assert played[1] == pytest.approx(source['startSec'] + .9, abs=.002)
        assert played[2] == pytest.approx(source['durationSec'], abs=.002)
    assert data == original
    assert tracks(result)['bass'][0][0] % 12 == 2


@pytest.mark.parametrize('bpm', [60, 150, 180])
def test_changing_bpm_does_not_stretch_humming(bpm):
    data = draft(bpm=bpm)
    store, sid = session(data)
    lead = tracks(store.render(sid, 1, 'r1'))['lead']
    assert [n[0] for n in lead] == [60, 64, 67, 64, 62]
    assert lead[0][1] == pytest.approx(data['inputs']['humming']['payload']['melody']['notes'][0]['startSec'], abs=.002)


def test_unknown_key_uses_only_drums_and_unmodified_lead():
    store, sid = session(draft(key=None))
    result = store.render(sid, 1, 'r1')
    assert result['state']['harmony']['key'] is None
    assert set(tracks(result)) == {'drums', 'lead'}
    assert len(tracks(result)['lead']) == 5


def test_combined_rhythm_controls_tempo_and_bass_positions():
    data = draft(combined=True, tempo_source='rhythm')
    store, sid = session(data)
    result = store.render(sid, 1, 'r1')
    assert result['tempo_bpm'] == data['inputs']['rhythm']['payload']['rhythm']['tempo_bpm']
    first = [n[1]*result['tempo_bpm']/60 for n in tracks(result)['bass'] if n[1] < 4*60/result['tempo_bpm']-.01]
    assert first == pytest.approx([0, 1, 1.5, 3], abs=.003)


def test_scoped_change_preserves_other_notes_and_retry_is_idempotent():
    store, sid = session()
    before = store.render(sid, 1, 'r1')
    after = store.render(sid, 1, 'r2', text='鼓更有力')
    for layer in ['lead', 'bass', 'keys']:
        assert tracks(before)[layer] == tracks(after)[layer]
    assert tracks(before)['drums'] != tracks(after)['drums']
    assert store.render(sid, 1, 'r2', text='鼓更有力') == after
    with pytest.raises(ValueError):
        store.render(sid, 1, 'r2', text='简化')


def test_simplify_and_bass_toggle_have_actual_effects():
    store, sid = session()
    before = store.render(sid, 1, 'r1')
    simple = store.render(sid, 1, 'r2', text='简化')
    assert len(tracks(simple)['drums']) < len(tracks(before)['drums'])
    assert tracks(simple)['lead'] == tracks(before)['lead']
    removed = store.render(sid, 1, 'r3', text='去掉贝斯')
    assert 'bass' not in tracks(removed)
    restored = store.render(sid, 1, 'r4', text='加上贝斯')
    assert tracks(restored)['bass'] == tracks(simple)['bass']


@pytest.mark.parametrize('settings', [
    {'bpm': 0}, {'bpm': True}, {'bpm': float('nan')}, {'melody_origin_s': 2},
    {'key': {'tonic': 12, 'mode': 'major'}}, {'placement_beats': -1},
    {'tempo_source': 'rhythm'},
])
def test_invalid_settings_preserve_music_but_invalidate_old_draft(settings):
    store, sid = session()
    with pytest.raises(ValueError):
        store.update(sid, 2, draft(**settings))
    with pytest.raises(ValueError):
        store.render(sid, 1, 'r1')
    store.update(sid, 3, draft())
    assert store.render(sid, 3, 'r1')['revision'] == 3


def test_combined_inputs_require_explicit_alignment():
    with pytest.raises(ValueError):
        session(draft(combined=True, alignment_confirmed=False))


def test_unsupported_or_conflicting_text_cannot_apply_partial_change():
    store, sid = session()
    before = store.render(sid, 1, 'r1')
    for text in ['鼓更有力，变成一只猫', '鼓更有力，鼓保持', '加速', '主旋律停止']:
        with pytest.raises(ValueError):
            store.render(sid, 1, 'bad'+text, text=text)
    assert tracks(store.render(sid, 1, 'r2')) == tracks(before)


def test_failed_render_retry_does_not_apply_control_twice(monkeypatch):
    store, sid = session()
    baseline = store.render(sid, 1, 'r1')
    execute = input_band.execute_render
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic backend failure')
    monkeypatch.setattr(input_band, 'execute_render', fail)
    with pytest.raises(RuntimeError):
        store.render(sid, 1, 'retry', text='鼓更有力')
    monkeypatch.setattr(input_band, 'execute_render', execute)
    result = store.render(sid, 1, 'retry', text='鼓更有力')
    old = next(x for x in baseline['state']['arrangement']['layers'] if x['name']=='drums')
    new = next(x for x in result['state']['arrangement']['layers'] if x['name']=='drums')
    assert new['level'] == old['level'] + .25


def test_draft_replacement_during_render_cannot_commit(monkeypatch):
    store, sid = session()
    entered, release = Event(), Event()
    execute = input_band.execute_render
    errors = []
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return execute(*args, **kwargs)
    monkeypatch.setattr(input_band, 'execute_render', delayed)
    def worker():
        try: store.render(sid, 1, 'old', text='鼓更有力')
        except ValueError as e: errors.append(str(e))
    thread = Thread(target=worker); thread.start()
    assert entered.wait(5)
    store.update(sid, 2, draft(bpm=90))
    release.set(); thread.join(10)
    assert errors and not thread.is_alive()
    monkeypatch.setattr(input_band, 'execute_render', execute)
    result = store.render(sid, 2, 'new')
    assert result['tempo_bpm'] == 90
    assert next(x for x in result['state']['arrangement']['layers'] if x['name']=='drums')['level'] == .5


def test_key_suggestion_does_not_change_selected_key():
    store, sid = session(draft(key=None))
    summary = store.update(sid, 2, draft(key=None))
    assert 'key_suggestion' in summary
    assert summary['key_suggestion']['ambiguous'], 'a five-note phrase is insufficient evidence for a confident key'
    assert store.render(sid, 2, 'r1')['state']['harmony']['key'] is None


def test_invalid_new_draft_also_cancels_inflight_old_revision(monkeypatch):
    store, sid = session()
    execute = input_band.execute_render
    def edit_during_render(*args, **kwargs):
        with pytest.raises(ValueError):
            store.update(sid, 2, draft(bpm=0))
        return execute(*args, **kwargs)
    monkeypatch.setattr(input_band, 'execute_render', edit_during_render)
    with pytest.raises(ValueError, match='未提交'):
        store.render(sid, 1, 'old', text='鼓更有力')
    monkeypatch.setattr(input_band, 'execute_render', execute)
    store.update(sid, 3, draft())
    result = store.render(sid, 3, 'new')
    assert next(x for x in result['state']['arrangement']['layers'] if x['name']=='drums')['level'] == .5


def test_one_pitch_has_no_key_suggestion():
    data = draft(key=None)
    melody = data['inputs']['humming']['payload']['melody']
    for group in [melody['notes'], melody['results']['raw']['notes'], melody['results']['cleaned']['notes']]:
        for note in group: note['pitchMidi'] = 60
    store, sid = session(data)
    assert store.update(sid, 2, data)['key_suggestion'] is None


@pytest.mark.parametrize('tonic,mode', [(0, 'major'), (7, 'major'), (9, 'minor')])
def test_selected_harmony_changes_accompaniment_without_transposing_source(tonic, mode):
    data = draft(key={'tonic': tonic, 'mode': mode})
    melody = data['inputs']['humming']['payload']['melody']
    for group in [melody['notes'], melody['results']['raw']['notes'], melody['results']['cleaned']['notes']]:
        for note in group:
            note['pitchMidi'] += tonic - (1 if mode == 'minor' and note['pitchMidi'] % 12 in {4, 9, 11} else 0)
    pitches = [n['pitchMidi'] for n in melody['notes']]
    store, sid = session(data)
    played = tracks(store.render(sid, 1, 'r1'))
    assert [n[0] for n in played['lead']] == pitches
    assert played['bass'][0][0] % 12 == tonic
    steps = {0,2,4,5,7,9,11} if mode == 'major' else {0,2,3,5,7,8,10}
    assert all((n[0]-tonic) % 12 in steps for layer in ['bass','keys'] for n in played[layer])


def test_saved_revision_can_reproduce_accumulated_adjustments():
    from jammate import web_session
    store, sid = session()
    store.render(sid, 1, 'r1', text='鼓更有力')
    result = store.render(sid, 1, 'r2', text='简化')
    assert hasattr(web_session, 'replay_revision'), 'saved revision replay not implemented'
    replayed = web_session.replay_revision(result)
    assert tracks(replayed) == tracks(result)
    assert replayed['state'] == result['state']
