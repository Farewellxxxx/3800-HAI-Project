"""Process-loading integration; no external LLM or MRT2 weights involved."""
from pathlib import Path
import json

import pytest

from jammate.reference_bridge import ReferenceBridge


ROOT = Path(__file__).resolve().parents[1]


def request(**changes):
    return {"session_id": "backend-bridge", "request_id": "one", "after_turn": 0,
            "text": "鼓更猛一点", "agent": "rule", "bpm": 100, "profile": "electric", **changes}


def test_workspace_bridge_loads_new_adapter_instead_of_pinned_snapshot(tmp_path):
    with ReferenceBridge(ROOT, scratch=tmp_path, implementation="workspace") as bridge:
        assert bridge._snapshot() == ROOT
        with pytest.raises(ValueError, match="MRT2 cannot guarantee") as error:
            bridge.request("text/turn", request(renderer="mrt2"))
        assert error.value.report["state_commit_allowed"] is False
        assert {item["constraint"] for item in error.value.report["preserve"]} >= {"tempo", "key"}
        # Strict backend rejection leaves the worker usable for another work.
        result = bridge.request("text/turn", request(session_id="exact", renderer="default"))
        assert result["implementation"] == "workspace" and result["reference_commit"] is None
        assert result["renderer"] == "原版合成器"
        assert result["wav"] and result["midi"]


def test_pinned_bridge_explicitly_refuses_unavailable_new_backend(tmp_path):
    with ReferenceBridge(ROOT, scratch=tmp_path, implementation="pinned") as bridge:
        with pytest.raises(ValueError, match="implementation workspace"):
            bridge.request("text/turn", request(renderer="mrt2"))


def test_audio_event_worker_uses_shared_contract_and_recoverable_mrt2_rejection(tmp_path):
    event = json.loads((ROOT / 'examples/input_events/humming.json').read_text())
    with ReferenceBridge(ROOT, scratch=tmp_path, implementation='workspace') as bridge:
        with pytest.raises(ValueError, match='MRT2 cannot guarantee'):
            bridge.request('input/render', {'event': event, 'renderer': 'mrt2'})
        result = bridge.request('input/render', {'event': event})
        assert result['input_event'] == event
        assert result['plan']['trigger_event_ids'] == [event['event_id']]
        assert result['state_after']['state_version'] > result['state_before']['state_version']
        assert result['wav'] and result['implementation'] == 'workspace'


def test_exact_text_event_is_returned_and_retry_does_not_reinterpret_it(tmp_path):
    body = request(text='  来一段，慢一点\n')
    with ReferenceBridge(ROOT, scratch=tmp_path, implementation='workspace') as bridge:
        first = bridge.request('text/turn', body)
        assert first['input_event']['payload']['text'] == body['text']
        assert first['input_event']['confidence'] is None
        assert bridge.request('text/turn', body) == first
