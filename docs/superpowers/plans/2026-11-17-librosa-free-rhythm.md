# Librosa Free Rhythm Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Track task status in `tmp/librosa-recovery/progress.md`. User approval authorizes execution without another approval round.

**Goal:** Exact upstream librosa recognition reused through the existing editable free-time InputEvent and MIDI path.

**Architecture:** Thin adapter around unchanged `analysis.rhythm._onsets_and_accents`; historical float32 mono mean, exact-time duplicate consolidation only. Retain `analyze_free_rhythm(audio, sample_rate) -> (list[float], list[float])`; bypass count-in/grid wrappers. No parameter/postprocessing changes to the upstream recognizer. The user's later explicit choice supersedes the earlier custom-candidate work, which stays only in ignored evidence snapshots.

**Tech Stack:** Existing Python/NumPy/SciPy/librosa, InputEvent 1.3, mido, existing JS editor and WSL workbench.

**Spec:** `docs/superpowers/specs/2026-11-17-librosa-free-rhythm.md`

## Global Constraints

- GPT-6 Astra only; no child-of-child delegation.
- No CUA, user-tab operations, commits, pushes, cleanup, migration or new worktrees.
- Reuse the complete upstream helper unchanged, including library defaults, gates, backtracking and peak-based accents; no custom detector or altered postprocessing.
- Preserve original seconds and strengths, unedited snapshot and output consistency; do not fabricate tempo/confidence.
- Preserve unrelated dirty work; private audio stays in ignored scratch.
- No parameter/postprocessing changes. Document exact-duplicate consolidation required by InputEvent, and inherited recognition limitations.

## Review Focus

1. Weak/fast hits and noise must match original behavior, with inherited errors visible in the benchmark.
2. Duplicate backtracked times must become one event at the exact same time without grouping nearby distinct hits.
3. No prepared count-in, BPM requirement, one-bar crop or grid snapping may enter the free path.
4. Original time zero, capture duration and upstream timing/strengths must survive JSON/MIDI adaptation.
5. Current event, playback, downloaded MIDI and downstream event must use identical accepted hits.

### Task 1: Restore exact upstream recognition

**Owner files:** `src/jammate/analysis/free_rhythm.py`, `tests/test_free_rhythm.py`; legacy `analysis/rhythm.py` and `tempo.py` must remain unchanged. Final report under `tmp/librosa-recovery/upstream-core-report.md`; the earlier `core-report.md` is historical custom-candidate evidence.

**Interface:** existing `analyze_free_rhythm(audio: ndarray, sample_rate: int) -> tuple[list[float], list[float]]`. Output sorted unique in-range seconds and matching finite positive normalized accents; empty evidence produces empty lists.

- [x] Preserve the custom candidate and prior evidence; audit original helper against a63a0f5 and record source hashes.
- [x] Demonstrate failing original-fidelity tests on the custom candidate, then implement the thin adapter. Test mono/stereo equivalence, exact duplicates and preservation of distinct close times.
- [x] Re-scope custom-accuracy tests transparently to original-fidelity or integration tests; retain frozen acoustic benchmark as the record of inherited quality limits.
- [x] Verify `tests/test_free_rhythm.py`, relevant legacy rhythm tests and original human recording; save machine-readable results and a compact comparison table in the final report.
- [x] Produce a final upstream-fidelity report and scoped diff, clearly superseding custom-candidate results. No commit.

### Task 2: Independent evidence and integration

**Owner files:** an isolated runner/fixture manifest under `tmp/librosa-recovery/evaluation/`, later an integration report under that directory. Do not edit Task 1 files.

**Consumes:** exact current detector API, preserved old source, unchanged legacy `_onsets_and_accents`, current `rhythm/analyze`, `rhythm/midi`, `input/render`.

- [x] Freeze labelled core and independent held-out cases before seeing final parameters. Use one-to-one matching; report precision/recall and timing with declared tolerances, accents separately. Human clip is unannotated.
- [x] Compare final adapter against original helper exactly and run the same quality cases; report inherited failures without presenting synthetic metrics as microphone accuracy.
- [x] Independently test exported MIDI roundtrip, event snapshot and existing JS edit/undo/invalidation behavior. Reuse existing tests; do not modify them to hide a mismatch.
- [x] After review, verify exact service ownership, restart only this workbench, replay real capture/example via HTTP, and verify generated pure MIDI and downstream plan/MIDI consistency. No need for MRT2 inference when only perception changed.

### Task 3: Review and delivery

**Owner:** fresh GPT-6 Astra reviewer; root owns docs and progress ledger.

- [x] Review scoped current-task diff against spec and independent results. Check correctness, hidden backend substitution, overfitting and integration.
- [x] Resolve evidenced defects through the implementer; recheck changed cases, not unbounded repeated full suites.
- [x] Update `docs/integration/LIBROSA_FREE_RHYTHM_20261117.md` and current workbench guidance with exact version/parameter evidence, remaining limitations and acceptance steps.
- [x] Verify final diff and service/API evidence, then report results honestly, including unresolved acoustic limitations.
