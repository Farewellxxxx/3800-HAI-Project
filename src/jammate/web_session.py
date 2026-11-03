"""Process-local revisions of one passage, not live transport.

Only a successful, still-current render replaces the committed StateManager.
Drafts retain original InputEvents; explicit placement is a separate mapping.
"""
from __future__ import annotations

import math
import time
from copy import deepcopy
from dataclasses import dataclass, field, replace
from threading import RLock
from uuid import uuid4

from jammate.analysis.key import estimate_key
from jammate.contracts import InputEvent, BandPlan
from jammate.contracts.adapters import from_text, to_legacy_phrase
from jammate.interaction import TransportPosition
from jammate.music import Key
from jammate.orchestration.agent import RuleAgent
from jammate.orchestration.manager import StateManager
from jammate.state import JamState


class SessionConflict(ValueError):
    pass


def replay_revision(receipt, *, fluidsynth=None, soundfont=None):
    """Reproduce a downloaded revision, including its prior layer adjustments."""
    previous = JamState.from_dict(receipt['state_before'])
    draft, _ = validate_draft({'inputs': receipt['inputs'], 'settings': receipt['settings']})
    sid, request_id = receipt['session_id'], receipt['request_id']
    if previous.session_id != sid:
        raise ValueError('保存记录中的会话不一致。')
    manager, plan, _ = SessionStore._prepare(sid, request_id, previous, draft, receipt.get('text', ''))
    from jammate.input_band import execute_render
    result = execute_render(manager, plan, fluidsynth=fluidsynth, soundfont=soundfont)
    return {**receipt, **result, 'state': manager.state.to_dict()}


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} 必须为 {low}–{high} 之间的有效数字。")
    return float(value)


def validate_draft(draft):
    if not isinstance(draft, dict) or set(draft) != {'inputs', 'settings'}:
        raise ValueError('无效的会话草稿。')
    inputs, settings = draft['inputs'], draft['settings']
    if not isinstance(inputs, dict) or set(inputs) - {'rhythm', 'humming'}:
        raise ValueError('会话只接受节拍与哼唱输入。')
    fields = {'tempo_source', 'bpm', 'key', 'melody_origin_s', 'placement_beats', 'alignment_confirmed'}
    if not isinstance(settings, dict) or set(settings) != fields:
        raise ValueError('请完整提供速度、调性与时间对齐设置。')
    events = {}
    for source, document in inputs.items():
        event = InputEvent.from_dict(document)
        if event.source != source:
            raise ValueError('输入类型与素材位置不一致。')
        if source == 'rhythm' and (event.payload['status'] != 'ready' or event.payload['rhythm']['confidence'] < .65):
            raise ValueError('节拍为空或与网格偏差过大，请重新识别。')
        if source == 'humming' and not 0 < len(event.payload['melody']['notes']) <= 4096:
            raise ValueError('请提供含有效音符的短哼唱。')
        events[source] = event
    source = settings['tempo_source']
    bpm = number(settings['bpm'], 'BPM', 60, 180)
    if source not in {'default', 'manual', 'rhythm'}:
        raise ValueError('未知速度来源。')
    if source == 'default' and bpm != 100:
        raise ValueError('默认速度为 100 BPM；自定义速度请选择手动。')
    if source == 'rhythm':
        if 'rhythm' not in events:
            raise ValueError('请先加入节拍，再采用节拍速度。')
        bpm = events['rhythm'].payload['rhythm']['tempo_bpm']
    key = settings['key']
    if key is not None:
        if not isinstance(key, dict) or set(key) != {'tonic', 'mode'} or type(key['tonic']) is not int or not 0 <= key['tonic'] < 12 or key['mode'] not in {'major', 'minor'}:
            raise ValueError('请选择有效的大调或小调。')
    origin = number(settings['melody_origin_s'], '录音第 0 拍秒数', 0, 30)
    placement = number(settings['placement_beats'], '会话放置拍数', 0, 64)
    if type(settings['alignment_confirmed']) is not bool:
        raise ValueError('请确认时间对齐方式。')
    if len(events) == 2 and not settings['alignment_confirmed']:
        raise ValueError('两段录音有独立零点，请确认对齐方式后再生成。')
    suggestion = None
    if 'humming' in events:
        phrase = to_legacy_phrase(events['humming'], tempo_bpm=bpm, beat_origin_s=origin, placement_beats=placement)
        recording_end = (events['humming'].payload['melody']['source']['durationSec'] - origin) * bpm / 60 + placement
        if max(recording_end, max(n.end for n in phrase.notes)) > 64 + 1e-8:
            raise ValueError('旋律与放置位置超过 16 小节，请缩短录音或减少偏移。')
        estimate = estimate_key(phrase.notes)
        if estimate:
            suggestion = {'key': {'tonic': estimate.key.tonic, 'mode': estimate.key.mode},
                          'score': estimate.score, 'margin': estimate.margin,
                          'ambiguous': len(phrase.notes) < 8 or sum(n.duration for n in phrase.notes) * 60 / bpm < 4 or estimate.score < .7 or estimate.margin < .1,
                          'meaning': '启发式候选，非正确概率；需手动确认，不自动应用。'}
    normalized = {'inputs': {k: e.to_dict() for k, e in events.items()},
                  'settings': {**deepcopy(settings), 'bpm': bpm, 'melody_origin_s': origin, 'placement_beats': placement}}
    return normalized, suggestion


@dataclass
class _Session:
    manager: StateManager
    revision: int = 0
    draft: dict | None = None
    touched: float = field(default_factory=time.monotonic)
    busy: bool = False
    completed: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)


class SessionStore:
    def __init__(self, *, fluidsynth=None, soundfont=None, max_sessions=8, ttl=7200):
        self.fluidsynth, self.soundfont = fluidsynth, soundfont
        self.max_sessions, self.ttl = max_sessions, ttl
        self._sessions, self._lock = {}, RLock()

    def _get(self, sid):
        session = self._sessions.get(sid)
        if session is None or (not session.busy and time.monotonic()-session.touched > self.ttl):
            self._sessions.pop(sid, None)
            raise SessionConflict('会话已过期或服务已重启，请新建会话并重新加入素材。')
        session.touched = time.monotonic()
        return session

    def create(self):
        with self._lock:
            now = time.monotonic()
            self._sessions = {sid: s for sid, s in self._sessions.items() if s.busy or now-s.touched <= self.ttl}
            if len(self._sessions) >= self.max_sessions:
                raise SessionConflict('本机会话数量已达上限，请关闭不用的会话后重试。')
            sid = uuid4().hex
            initial = JamState(session_id=sid, key=None, tempo_bpm=100)
            initial = initial.with_updates(layers=tuple(replace(x, active=False) if x.name in {'bass','keys'} else x for x in initial.layers))
            self._sessions[sid] = _Session(StateManager(initial))
            return {'session_id': sid, 'revision': 0, 'agent': 'rule', 'persistence': 'process_local'}

    def close(self, sid):
        with self._lock:
            self._sessions.pop(sid, None)

    def update(self, sid, revision, draft):
        if type(revision) is not int or revision < 1:
            raise ValueError('无效的草稿版本。')
        with self._lock:
            session = self._get(sid)
            if revision < session.revision:
                raise SessionConflict('草稿已被较新的修改替代。')
            if revision > session.revision:
                # Even a temporarily invalid edit cancels work on an older draft.
                session.revision, session.draft = revision, None
            data, suggestion = validate_draft(draft)
            if session.draft is not None and data != session.draft:
                raise SessionConflict('草稿已被较新的修改替代。')
            session.revision, session.draft = revision, data
            return {'session_id': sid, 'revision': revision, 'settings': data['settings'], 'key_suggestion': suggestion}

    def render(self, sid, revision, request_id, *, text=''):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or not isinstance(text, str) or len(text) > 500:
            raise ValueError('无效的请求标识或过长的指令。')
        identity = (revision, text)
        with self._lock:
            session = self._get(sid)
            if type(revision) is not int or revision != session.revision or session.draft is None:
                raise SessionConflict('请先同步当前草稿，再生成。')
            if request_id in session.completed:
                if session.completed[request_id] != identity:
                    raise SessionConflict('请求标识已用于另一条指令。')
                if request_id not in session.cache:
                    raise SessionConflict('该操作已执行，试听缓存已释放；请生成新版本，不要重复应用。')
                return deepcopy(session.cache[request_id])
            if session.busy:
                raise SessionConflict('上一轮还在结束，请稍后重试当前操作。')
            if len(session.completed) >= 64:
                raise SessionConflict('会话已达 64 次生成上限，请下载结果并新建会话。')
            data = deepcopy(session.draft)
            previous = session.manager.state
            session.busy = True
        try:
            manager, plan, events = self._prepare(sid, request_id, previous, data, text)
            from jammate.input_band import execute_render
            output = execute_render(manager, plan, fluidsynth=self.fluidsynth, soundfont=self.soundfont)
            result = {**output, 'session_id': sid, 'revision': revision, 'request_id': request_id,
                      'state': manager.state.to_dict(), 'state_before': previous.to_dict(), 'settings': data['settings'],
                      'inputs': data['inputs'], 'events': [e.to_dict() for e in events],
                      'text': text, 'timeline': 'revision_of_same_passage_from_bar_zero'}
            with self._lock:
                if self._sessions.get(sid) is not session or session.revision != revision:
                    raise SessionConflict('生成期间素材或设置已改变，本次结果未提交。')
                session.manager = manager
                session.completed[request_id] = identity
                session.cache[request_id] = result
                while len(session.cache) > 2:
                    del session.cache[next(iter(session.cache))]
                return deepcopy(result)
        finally:
            with self._lock:
                session.busy = False
                session.touched = time.monotonic()

    @staticmethod
    def _prepare(sid, request_id, previous, data, text):
        settings = data['settings']
        if not data['inputs']:
            raise ValueError('请先加入哼唱或节拍。')
        key = Key(**settings['key']) if settings['key'] else None
        layers = previous.layers
        if key is None:
            layers = tuple(replace(x, active=False) if x.name in {'bass','keys'} else x for x in layers)
        elif previous.key is None:
            layers = tuple(replace(x, active=True) if x.name in {'bass','keys'} else x for x in layers)
        state = previous.with_updates(tempo_bpm=settings['bpm'], key=key, layers=layers,
            position=TransportPosition(), motifs=(), current_motif_id=None, last_user_motif=(),
            last_ai_motif=(), rhythm=previous.rhythm if 'rhythm' in data['inputs'] else None, rhythm_sources=(),
            interaction=replace(previous.interaction, user_active=False, awaiting_user=False))
        manager = StateManager(state)
        events, placements = [], {}
        for source, original in data['inputs'].items():
            document = {**original, 'session_id': sid, 'event_id': f'{request_id}:{source}',
                        'started_at': None, 'ended_at': None}
            event = InputEvent.from_dict(document)
            events.append(event)
            if source == 'humming':
                placements[event.event_id] = {'beat_origin_s': settings['melody_origin_s'], 'placement_beats': settings['placement_beats']}
        if text.strip():
            events.append(from_text(text, session_id=sid, event_id=f'{request_id}:text'))
        accepted = manager.ingest(events, placements=placements)
        observed, history = manager.decision_snapshot()
        plan = RuleAgent().decide(accepted, observed, plan_id=f'web_{request_id}', history=history)
        decision = plan.to_dict()
        if decision['unresolved']:
            raise ValueError('指令未执行：' + '；'.join(decision['unresolved']))
        if decision['transport'] or any(a['action'] in {'VARY_MOTIF','INTRODUCE_MOTIF'} or (a['scope']=='lead' and a['action'] not in {'ECHO_MOTIF','PRESERVE'}) for a in decision['actions']):
            raise ValueError('此工作台保留输入旋律；请用速度设置调整 BPM，用播放按钮停止试听。')
        if 'humming' in data['inputs']:
            duration = data['inputs']['humming']['payload']['melody']['source']['durationSec']
            end = (duration-settings['melody_origin_s'])*settings['bpm']/60 + settings['placement_beats']
            plan = BandPlan.from_dict({**decision, 'valid_for_bars': max(decision['valid_for_bars'], math.ceil(end/4-1e-9))})
        manager.stage(plan)
        return manager, plan, events
