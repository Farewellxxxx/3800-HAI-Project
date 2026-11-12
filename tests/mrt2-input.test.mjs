import assert from 'node:assert/strict';
import test from 'node:test';
import { prepareMrt2Input } from '../web/mrt2-input.js';

test('text handoff preserves spaces and punctuation without requiring MIDI', () => {
  const prompt = '  温暖的 lo-fi\n别加贝斯。  ';
  const input = prepareMrt2Input('text', {prompt});
  assert.equal(input.prompt, prompt);
  assert.equal(input.midi_base64, null);
});

test('humming handoff preserves the exact MIDI bytes', () => {
  const midi = Uint8Array.of(77, 84, 104, 100, 0, 255);
  const input = prepareMrt2Input('humming', {midi, duration: 4.4});
  assert.deepEqual([...Buffer.from(input.midi_base64, 'base64')], [...midi]);
  assert.equal(input.duration_s, 4.4);
});
