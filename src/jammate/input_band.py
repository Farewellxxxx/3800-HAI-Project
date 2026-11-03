"""Render one independent web clip through the team's versioned Agent loop."""
from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from uuid import uuid4

import soundfile as sf

from jammate.contracts import InputEvent
from jammate.orchestration.agent import RuleAgent
from jammate.orchestration.manager import StateManager
from jammate.orchestration.offline import OfflineRuntime
from jammate.render.midi_out import to_pretty_midi
from jammate.state import JamState


def render_clip(document, *, fluidsynth=None, soundfont=None):
    event = InputEvent.from_dict(document)
    payload = event.payload
    if event.source == "rhythm":
        tempo = payload["rhythm"]["tempo_bpm"]
        if payload["status"] != "ready" or payload["rhythm"]["confidence"] < 0.65:
            raise ValueError("拍点不足或与网格偏差过大，请重新拍一小节。")
    elif event.source == "humming":
        tempo = 100.0
        if not payload["melody"]["notes"]:
            raise ValueError("这段录音没有识别到音符，请重新哼唱或切换识别结果。")
    else:
        raise ValueError("此入口需要哼唱或节奏事件。")

    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=tempo))
    accepted = manager.ingest([event])
    state, history = manager.decision_snapshot()
    plan = RuleAgent().decide(accepted, state, plan_id=f"band_{uuid4().hex}", history=history)
    if plan.to_dict()["strategy"] != "RESPOND":
        raise ValueError("乐队无法用这段输入生成回应，请尝试更短的乐句或更清晰的节奏。")
    manager.stage(plan)
    return {"event_id": event.event_id, **execute_render(manager, plan, fluidsynth=fluidsynth, soundfont=soundfont)}


def execute_render(manager, plan, *, fluidsynth=None, soundfont=None):
    """Execute a staged plan and export the same performance on a local timeline."""
    if fluidsynth is not None:
        from renderer_experiments.app.band_plan import KevinRuntime

        with tempfile.TemporaryDirectory() as directory:
            runtime = KevinRuntime(Path(directory), executable=fluidsynth, soundfont=soundfont)
            result = runtime.execute(manager, plan)
            wav = (runtime.last_artifacts / "band.wav").read_bytes()
            midi = (runtime.last_artifacts / "band.mid").read_bytes()
            warnings = runtime.last_receipt["persistence_warnings"]
        renderer = "Kevin / FluidSynth"
    else:
        result = OfflineRuntime().execute(manager, plan)
        wav_buffer, midi_buffer = io.BytesIO(), io.BytesIO()
        sf.write(wav_buffer, result.audio, result.sample_rate, format="WAV", subtype="PCM_16")
        from pretty_midi import Text
        midi_document = to_pretty_midi(tuple(n.shifted(-result.start_bar * 4) for n in result.notes), result.tempo_bpm)
        midi_document.text_events.append(Text('JamMate passage end', result.bars * 4 * 60 / result.tempo_bpm))
        midi_document.write(midi_buffer)
        wav, midi = wav_buffer.getvalue(), midi_buffer.getvalue()
        renderer, warnings = "JamMate / NumPy", []
    return {
        "plan": plan.to_dict(), "bars": result.bars,
        "tempo_bpm": result.tempo_bpm, "renderer": renderer, "agent": "rule",
        "warnings": warnings, "manager_diagnostics": manager.diagnostics(),
        "wav": base64.b64encode(wav).decode("ascii"), "midi": base64.b64encode(midi).decode("ascii"),
    }


from jammate.web_session import SessionStore  # public web service alongside render_clip
