# Free Rhythm Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans within the assigned scope. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record, edit and play a free rhythm and make the selected rhythm available to the shared JamMate band.

**Architecture:** Preserve one authoritative edited seconds timeline with raw detector evidence. Convert to timed General MIDI percussion for direct playback/export and adopt the same event into the Harness for arrangement.

**Tech Stack:** Python, NumPy, SciPy, JSON Schema, pretty_midi, mido, JavaScript and browser Computer Use verification.

**Spec:** `docs/superpowers/specs/2026-11-17-free-rhythm-design.md`

## Global constraints

- Preserve the dirty humming work. Keep the historical one-bar contract and playback path. Use the existing Windows/WSL environments and leave publication to the user.
- The capture window is 0.5 to 30 seconds at 8–96 kHz, its timebase is recording-relative seconds, and MIDI uses a nominal 120 BPM.

## Review focus

- Quiet attacks next to louder attacks survive local thresholds without stationary noise producing a beat.
- A fixed-length recording containing mostly silence keeps its full range in capture and playback.
- Editing all hits out disables generation, while an edit retains original evidence.
- A phrase longer than eight arrangement bars and a newly adopted phrase at nonzero transport bar both retain their anchors.
- Hits immediately before a bar line retain sounding MIDI notes in the NumPy, FluidSynth and MRT2 adapter paths. Continued turns on an adopted rhythm repeat the full phrase period.
- Current and legacy Python/BandPlan/renderer tests still pass.

## Tasks

1. Capture, schema and MIDI (`analysis/free_rhythm.py`, `contracts/input_event.*`, `contracts/adapters.py`, `scripts/reference_worker.py`, `tests/test_free_rhythm.py`).
   - [x] Write failing WAV, schema and pure MIDI tests for `rhythm/analyze` and `rhythm/midi`.
   - [x] Implement free detection, validated event construction and pure MIDI while preserving old requests.
   - [x] Verify those cases in the complete Python suite and region-specific pinned/workspace route regression.
2. Shared band (`rhythm.py`, `state.py`, `contracts/state_codec.py`, `orchestration/`, `generate/`, `input_band.py`).
   - [x] Write a failing render test that adopts a free rhythm extending beyond bar eight and checks the MIDI anchor times, and a nonzero transport test.
   - [x] Register the free seed, project the adoption phase, arrange without quantizing, expand the response length and report its arrangement tempo.
   - [x] Run `.venv/Scripts/python.exe -m pytest -q -o addopts=''` and `git diff --check`.
3. Recording page (`web/rhythm.*`, browser regressions, free rhythm example).
   - [ ] Test the record-to-edit, MIDI, arrangement and stale-result paths.
   - [ ] Connect the timeline and audition to one immutable selected event per revision.
   - [ ] Run the browser checks on the integrated local workspace server.
