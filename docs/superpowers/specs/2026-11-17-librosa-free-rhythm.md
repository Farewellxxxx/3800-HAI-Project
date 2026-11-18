# Approved scope: librosa free-rhythm recovery

The user approved execution on 2026-11-17 and then explicitly selected: **原样复用整段识别函数，只移除定速、截小节和量化包装**. This latest choice supersedes the earlier permission to tune librosa parameters and postprocessing. Only GPT-6 Astra may implement, evaluate or review this work. No Sol workers may be resumed.

## Required behavior

Record/import a free phrase in the existing rhythm page, detect it and obtain an editable percussion MIDI. No count-in, mandatory BPM, one-bar crop or forced grid. Preserve original-clock timing, rests and relative attack strengths. Existing capture limits stay unchanged. The default is one result, not a new menu of competing algorithms.

Call the unchanged upstream `jammate.analysis.rhythm._onsets_and_accents` directly, with the historical float32 mono conversion. Preserve every original librosa argument/default, padding/backtracking rule, whole-clip gate, 60 ms peak strength and 12% recording-global filter. Do not tune or add spectral bands, filters, local energy/decay rules, onset refinement or close-hit merging. `analysis/rhythm.py` and `analysis/tempo.py` must stay identical to the referenced a63a0f5 version. Bypass only the outer `analyze_rhythm_audio` count-in/tempo and `rhythm_from_onsets` one-bar/grid wrappers.

Representation-only adaptation: convert NumPy scalars/arrays to JSON-compatible lists and consolidate **exactly equal** onset timestamps, keeping their maximum accent, because the existing free InputEvent requires unique times. No tolerance, snapping or new threshold is allowed; all distinct times and their accents remain unchanged. Historical stereo downmix is the channel mean, not a new phase-preserving spectral combination. Document this adapter policy explicitly.

Keep InputEvent 1.3.0 and the existing editor/MIDI chain unless an evidenced defect requires a compatible fix. Current audition, exported MIDI and InputEvent must share the same accepted/edited hits. Raw detections remain available as the initial unedited snapshot. No invented BPM or calibrated confidence. MIDI's encoding tempo is not detected tempo. Keep Harness/MRT2 compatibility, but model-generated sound is not evidence of onset accuracy or velocity fidelity.

## Evidence and limitations

The preserved 7.14 s human recording is `tmp/free-rhythm/clap-failure-mono-mean.wav`; original WebM, original 105-hit event and old detector source are alongside it. Old RMS logic exactly reproduced 105 onsets; legacy librosa plus its project gate returned 10 candidates. Neither 10 nor any new count is annotated intent ground truth. Preserve these artifacts; do not commit private audio.

Evaluation covers real capture, existing examples, weak-after-loud, rapid double strikes, irregular timing, long rests, resonant low taps, stationary/modulated noise, clip boundaries, gain and sample-rate changes. Acceptance now means exact upstream detection fidelity (apart from documented exact-duplicate representation), working free timeline and correct output roundtrips. Retain the already frozen quality benchmark and report inherited misses/extras honestly; do not modify upstream to make it pass improved-detector accuracy targets. Tests that assumed the superseded custom detector's accuracy must be explicitly re-scoped to upstream equivalence or data integration, not silently loosened and claimed as quality improvements.

## Operating boundaries

Continue in the existing C-drive linked worktree. Disk cleanup/migration is deferred to another chat. Preserve unrelated dirty changes; no broad reset/clean, commits, pushes, upload or unrelated dependencies. No Computer Use and no interaction with the user's browser tabs. Use offline scripts, HTTP and isolated tests. The exact workspace service may be restarted after validation and process/port ownership checks, without refreshing the user's page.

Deliver flow comparison, changed files, exact detector/parameter decisions, before/after evidence, remaining failure cases, MIDI/InputEvent checks, service status and concrete user acceptance steps. User approval already authorizes ordinary implementation/testing decisions within this scope.
