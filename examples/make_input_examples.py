"""Reproducible synthetic audio, never a claim of human-recording accuracy."""
from pathlib import Path
from math import exp, pi, sin
from random import Random
import struct
import wave

import numpy as np
from jammate.input_event import perceive_rhythm, write_event

ROOT=Path(__file__).resolve().parents[1]
sr=22050
audio=np.zeros(sr*6,dtype=np.float32)
rng=np.random.default_rng(7)
for t,a in zip([.6,1.2,1.8,2.4,3,3.6,3.9,4.8],[1,1,1,1,1,.55,.8,1]):
    start=round(t*sr);n=round(.03*sr)
    audio[start:start+n]+=rng.standard_normal(n)*np.exp(-np.linspace(0,6,n))*.25*a
write_event(perceive_rhythm(audio,sr,session_id='synthetic-example'),ROOT/'examples/input_lab_events/rhythm.json')

# The web demo has no count-in. A quieter reflection is part of each attack.
free_sr = 16000
random = Random(44821)
free_audio = [random.uniform(-.0024, .0024) for _ in range(round(free_sr * 7.15))]
for at, strength in [(0.41, .72), (.84, .24), (1.23, .70), (1.92, .22), (2.07, .67),
                     (3.46, .20), (3.82, .69), (4.57, .045), (5.19, .73), (6.52, .25)]:
    for delay, gain in [(0, 1), (.026, .19)]:
        start = round(at * free_sr) + round(delay * free_sr)
        for i in range(round(.022 * free_sr)):
            t = i / free_sr
            signal = .7 * random.uniform(-1, 1) + .3 * sin(2 * pi * 291 * t)
            free_audio[start + i] += gain * strength * exp(-t / .006) * signal
with wave.open(str(ROOT / 'web/rhythm-example.wav'), 'wb') as wav:
    wav.setparams((1, 2, free_sr, 0, 'NONE', 'not compressed'))
    wav.writeframes(struct.pack(f'<{len(free_audio)}h', *(round(x * 32767) for x in free_audio)))
print('Generated synthetic rhythm example and InputEvent')
