"""Create a passage from one input through the team's versioned Agent loop."""
from __future__ import annotations

import base64
import io
import tempfile
import time
from uuid import uuid4

import soundfile as sf

from jammate.contracts import BandPlan, InputEvent
from jammate.contracts.adapters import from_text
from jammate.contracts.input_event import FREE_RHYTHM_EVENT_VERSION
from jammate.music import BEATS_PER_BAR
from jammate.orchestration.agent import RuleAgent
from jammate.orchestration.manager import StateManager
from jammate.render.free_rhythm_midi import free_rhythm_ticks
from jammate.render.midi_out import to_pretty_midi, write_arrangement_midi
from jammate.render.runtime import create_runtime
from jammate.rhythm import RhythmMode
from jammate.state import JamState


FREE_RHYTHM_ARRANGEMENT_BPM = 120.0


def render_clip(document, *, creative=False, fluidsynth=None, soundfont=None,
                backend="default", allow_preview=False, mode=None, bars=None, energy=1):
    """One explicit demo take, through the shared Harness and runtime factory.

    Mode/energy/bars are user-selected demo settings, never perception fields.
    The session tempo initialization below is this demo's policy, not a change
    made by the input adapter or a parallel persistent JamState.
    """
    started = time.perf_counter()
    if backend not in {"default", "fluidsynth", "mrt2"} or type(allow_preview) is not bool:
        raise ValueError("无效的渲染后端或试听选项。")
    if type(energy) is not int or not 0 <= energy <= 3:
        raise ValueError("力度需为 0–3。")
    if bars is not None and (type(bars) is not int or not 1 <= bars <= 8):
        raise ValueError("请选择 1–8 小节。")
    if creative and isinstance(document, dict) and set(document) == {"text"}:
        text = document["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 500:
            raise ValueError("请输入 1–500 字的创作提示。")
        event = from_text(text, session_id=f"creation_{uuid4().hex}")
    else:
        event = InputEvent.from_dict(document)
    payload = event.payload
    free_rhythm = event.schema_version == FREE_RHYTHM_EVENT_VERSION
    expected_strategy = "RESPOND"
    if free_rhythm:
        if payload["status"] != "ready":
            raise ValueError("请先添加或识别至少一个拍点。")
        tempo = FREE_RHYTHM_ARRANGEMENT_BPM
        free_rhythm_ticks(payload["rhythm"]["onset_seconds"], payload["audio_duration_s"], tempo)
    elif event.source == "rhythm":
        tempo = payload["rhythm"]["tempo_bpm"]
        if payload["status"] != "ready" or payload["rhythm"]["confidence"] < 0.65:
            raise ValueError("拍点不足或与网格偏差过大，请重新拍一小节。")
    elif event.source == "humming":
        tempo = 100.0
        if not payload["melody"]["notes"]:
            raise ValueError("这段录音没有识别到音符，请重新哼唱或切换识别结果。")
    elif creative and event.source == "text":
        tempo = 100.0
        expected_strategy = "INITIATE"
    else:
        raise ValueError("此入口需要哼唱或节奏事件。")

    rhythm_mode = RhythmMode(mode) if mode is not None else (
        RhythmMode.VARY if creative and event.source == "rhythm" and not free_rhythm else RhythmMode.FOLLOW)
    manager = StateManager(JamState(session_id=event.session_id, tempo_bpm=tempo,
                                   rhythm_mode=rhythm_mode, energy=energy))
    accepted = manager.ingest([event])
    state, history = manager.decision_snapshot()
    plan = RuleAgent().decide(accepted, state, plan_id=f"band_{uuid4().hex}", history=history, vary_input=creative)
    # The existing rhythm page explicitly chooses its demo length. No motif is
    # shortened, and the team's Agent still owns every strategy/action.
    if bars is not None and event.source == "rhythm":
        plan_data = plan.to_dict()
        plan_data["valid_for_bars"] = max(bars, plan_data["valid_for_bars"]) if free_rhythm else bars
        plan = BandPlan.from_dict(plan_data)
    decision = plan.to_dict()
    if decision["unresolved"]:
        raise ValueError("指令未执行：" + "；".join(decision["unresolved"]))
    if decision["strategy"] != expected_strategy:
        if event.source == "text":
            raise ValueError("请用「来一段」开始创作，可以加上「快一点」或「慢一点」。")
        raise ValueError("乐队无法用这段输入生成回应，请尝试更短的乐句或更清晰的节奏。")
    manager.stage(plan)
    planned = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        runtime = create_runtime(directory, backend=backend, fluidsynth=fluidsynth,
                                 soundfont=soundfont, allow_preview=allow_preview)
        result = runtime.execute(manager, plan)
        receipt = getattr(runtime, "last_receipt", None)
        if getattr(runtime, "last_artifacts", None) is not None:
            wav = (runtime.last_artifacts / "band.wav").read_bytes()
            midi = (runtime.last_artifacts / "band.mid").read_bytes()
        else:
            wav_buffer, midi_buffer = io.BytesIO(), io.BytesIO()
            sf.write(wav_buffer, result.audio, result.sample_rate, format="WAV", subtype="PCM_16")
            if free_rhythm:
                write_arrangement_midi(result.notes, result.tempo_bpm, midi_buffer,
                                       resolution=result.midi_resolution, duration_beats=result.bars * BEATS_PER_BAR)
            else:
                to_pretty_midi(result.notes, result.tempo_bpm).write(midi_buffer)
            wav, midi = wav_buffer.getvalue(), midi_buffer.getvalue()
    renderer = "MRT2 / generated preview" if backend == "mrt2" else (
        "Kevin / FluidSynth" if fluidsynth else "JamMate / NumPy")
    warnings = receipt.get("persistence_warnings", []) if receipt else []
    return {
        "event_id": event.event_id, "plan": plan.to_dict(), "bars": result.bars,
        "input_event": event.to_dict(), "receipt": receipt,
        "state_before": state.to_dict(), "state_after": manager.state.to_dict(),
        "mode": rhythm_mode.value,
        "timing_s": {"intake_and_plan": planned-started, "render_and_encode": time.perf_counter()-planned},
        "tempo_bpm": result.tempo_bpm, "renderer": renderer, "agent": "rule",
        **({"tempo_source": "arrangement_default"} if free_rhythm else {}),
        "warnings": warnings, "manager_diagnostics": manager.diagnostics(),
        "wav": base64.b64encode(wav).decode("ascii"), "midi": base64.b64encode(midi).decode("ascii"),
    }
