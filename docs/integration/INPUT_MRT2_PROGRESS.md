# Execution ledger — 2026-11-14 input-mrt2

Plan: ../superpowers/plans/2026-11-14-input-mrt2.md

- Baselines: local 3d32fcd, team 5dc9fb8. Dirty E:/.../JamMate-mrt2-inputs preserved. Native worktree created at C:/Users/Hanson/.codex/worktrees/jammate-input-mrt2/3800-HAI-Project, branch feature/input-event-mrt2.
- Team backend merged without textual conflicts. Merge is baseline integration, not evidence of runtime success.
- Initial baseline test collection failed: reused Windows venv lacks jsonschema. Preparing isolated Windows venv and WSL model environment.
- Local hardware: RTX 4050 Laptop 6 GiB; WSL Ubuntu Python 3.12, 7.6 GiB RAM. Team's 4060/8 GiB validation is historical evidence only.
- Ruling: retain original text source=text/event_type=speech extension already in team Contract — avoid falsely labelling typed text as ASR — requires documenting SPEC enum extension.
- Ruling: retain historical baseline demo/legacy export APIs while main optimized/rhythm paths use shared orchestration — preserve reproducibility — old auxiliary paths remain explicitly historical.
- Ruling: user approved execution without extra plan gates; implementation proceeds inline — scope is fixed by accepted prompt — any material deviation is recorded here.
- Pre-flight: Task 1 produces canonical event consumed by Task 2 and Task 3. Task 2 adds backend and trace fields consumed by Task 3/4; preview receipts remain owned by existing runtime.
- Task 1 complete: canonical humming event RED (missing schema_version) → GREEN; commit f1ca81a. Downloads and submission use identical selected melody evidence.
- Task 2 complete: backend/preview tests RED (unexpected backend keyword) → GREEN; shared input/render and factory, raw text and state/receipt trace added. Full Python suite 466 passed (tmp/pytest-all.xml).
- Task 3 complete: browser RED exposed trimmed original text → GREEN; backend controls, trace downloads and stale-result invalidation implemented. Real NumPy and real MRT2 three-page checks passed; 33 Node tests passed. Old navigation, lifecycle, async, input-browser, creation-text and mrt2-input suites passed. Initial lifecycle timeout disappeared on diagnostic rerun; original recorder unchanged. Creation-text required the existing FluidSynth binary and its stale-output expectations were updated to the intended behavior.
- Task 4 implementation complete: isolated official magenta-rt 2.0.3/JAX CUDA12 environment; ten model hashes match; real MRT2 rendered all three inputs on RTX 4050 6 GiB and browser decoded/played all three. Cold 62.94 s, warm 5.69/5.29 s. No human microphone/listening claim. Synthetic rhythm 12/12, two negative cases rejected; full comparison and evidence persisted.
- Ruling: keep the runnable worktree, plan and ledger for handoff instead of deleting the plan workspace after review — user explicitly requested a locally runnable result — costs only local disk space.
- Next: one independent final review, fix material findings with regression tests, commit locally; no push.
- Final review: independent fresh-context reviewer (gpt-6-astra), ec310aa..60ac9e7 plus LF/label follow-ups; no Critical/Important findings. Reviewer ran targeted tests and verified all saved real events/trace IDs, state equality, MIDI hashes and stereo WAV metadata.
- Final: minor playback-clock assertion was already added independently before the review result arrived; final real browser run now enforces it and exact downloaded text event. No production behavior changed.
- Final: Ruling: correct the report's input-invalidation wording immediately rather than defer an inaccurate claim — text editing retains the prior turn until submission, unlike changing an audio take — documentation accuracy, no runtime change.
- Final: Ruling: reviewer declined human microphone/listening/physical-speaker judgments and independent GPU reproduction — report excludes those human claims; author supplies two actual GPU/browser runs with explicit receipts — no general accuracy or audio-fidelity guarantee.
- Final: keep local named branch/worktree per existing user authorization (finishing-a-development-branch keep-as-is); no additional integration menu or push.
- Final real browser rerun: 3/3 passed with the strengthened playback-clock and exact text-download assertions; evidence persisted in examples/input_mrt2/validation.json. Both original cold-run fixtures and final rerun are real_magenta_rt.
- Deferred minors: none; the pre-review test addition covers the first observation, and factual documentation correction covers the second. No material production-code fix was needed.
