# Free rhythm design

JamMate accepts a short percussion recording as an expressive phrase. The player can tap, clap or beatbox in their own time, see/edit detected hits and accents, play the resulting percussion, download MIDI and send that same edited phrase to the band.

## Chosen approach

Keep the established InputEvent envelope and use version `1.3.0` for a rhythm seed measured in recording-relative seconds. Extending the old beat grid would still require an inferred or manually supplied tempo. Performing directly from a seconds timeline preserves the phrase and its leading and trailing rests. The existing single-bar/count-in contract remains available for legacy callers.

`payload` contains `audio_duration_s`, `status`, `rhythm` and `raw_rhythm`. Both rhythm objects contain strictly increasing `onset_seconds` and corresponding `accents` in `(0, 1]`. Time zero is the start of the original recording. Each onset is strictly before its end. Raw detections travel with the selected hits. An edit uses a fresh event ID and changes only the selected hits and their status. `status` is `ready` when there are selected hits and `no_onsets` otherwise. Uncalibrated confidence is `null`. Capture timestamps are either a session interval matching the original duration or both `null`.

The recorder accepts clips between 0.5 and 30 seconds at 8–96 kHz. Transient detection uses a locally adaptive onset threshold and relative strength normalization. The detector does not require a steady pulse, tempo, meter or grid. Source and MIDI auditions start at the recording's zero. Pure percussion export uses General MIDI drum note 36 and velocity `max(1, round(accent * 127))`. The 120 BPM in the MIDI file encodes seconds and carries no tempo inference.

The shared Harness registers and adopts the selected phrase via `ADJUST_FEEL`. The new recording demo initializes arrangement tempo to 120 BPM and labels it as an arrangement default. In an existing session, the current session tempo determines where bar boundaries fall. Follow preserves hit anchors. Vary can add decoration and simplify can remove hits. The default response covers one full capture including rests. Continued jam turns and explicit longer arrangements repeat the complete phrase on its whole-bar period, preserving its timing and rests. The source timeline and pure MIDI still span one original capture. The legacy arranger, one-bar analyzer and text/humming flows retain their existing interfaces.

## Acceptance

- The recording, selected timeline and percussion MIDI agree after adding, moving, deleting and re-accenting hits.
- A recording can contain one hit, irregular or closely spaced rhythms, or several bars without a count-in. Silence is editable and cannot trigger creative rendering until it has selected hits.
- A longer phrase is adopted by the shared Harness and rendered without first-bar repetition or last-hit truncation. Supported preview backends may interpret the conditioning differently from the precise renderer.
- Existing saved InputEvents and JamState documents continue to load.
