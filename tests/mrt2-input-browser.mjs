import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const {Midi} = createRequire(new URL('../web/optimized/package.json', import.meta.url))('@tonejs/midi');
const root = path.resolve(import.meta.dirname, '..');
const base = process.env.INPUT_LAB_URL || 'http://127.0.0.1:4188';
const browser = await chromium.launch({channel: 'msedge', headless: true, downloadsPath: path.join(root, 'tmp/browser')});
const page = await browser.newPage({acceptDownloads: true});
const errors = [];
page.on('pageerror', error => errors.push(error.message));

async function download(selector) {
  const [file] = await Promise.all([page.waitForEvent('download'), page.locator(selector).click()]);
  return readFile(await file.path());
}

async function input(selector, source) {
  const result = JSON.parse(await download(selector));
  assert.equal(result.schema_version, 1);
  assert.equal(result.source, source);
  return result;
}

try {
  await page.goto(base + '/rhythm.html');
  await page.locator('#example').click();
  await page.locator('#analyze').click();
  await page.locator('#result').waitFor();
  const before = await download('#rhythm-mrt2-midi');
  const originalEvent = JSON.parse(await download('#download-event'));
  await page.locator('#hit-time').fill('0.5');
  await page.locator('#hit-velocity').fill('43');
  await page.locator('#save-hit').click();
  const editedEvent = JSON.parse(await download('#download-event'));
  assert.notEqual(editedEvent.event_id, originalEvent.event_id);
  assert.deepEqual(editedEvent.payload.raw_rhythm, originalEvent.payload.raw_rhythm);
  assert.equal(editedEvent.payload.rhythm.accents[0], 43 / 127);
  const hits = await input('#rhythm-mrt2-export', 'rhythm_hits');
  const hitsBytes = Buffer.from(hits.midi_base64, 'base64');
  assert.notDeepEqual(hitsBytes, before);
  assert.deepEqual(await download('#rhythm-mrt2-midi'), hitsBytes);
  assert.equal(hits.duration_s, editedEvent.payload.audio_duration_s);
  const tracks = new Midi(hitsBytes).tracks.filter(track => track.notes.length);
  assert.equal(tracks.length, 1);
  assert.equal(tracks[0].channel, 9);
  assert.equal(tracks[0].notes.length, editedEvent.payload.rhythm.onset_seconds.length);
  assert.equal(tracks[0].notes[0].time, .5);
  assert.equal(Math.round(tracks[0].notes[0].velocity * 127), 43);
  tracks[0].notes.forEach((note, index) => {
    assert(Math.abs(note.time - editedEvent.payload.rhythm.onset_seconds[index]) < .00003);
  });

  await page.locator('#arrangement > summary').click();
  await page.locator('[data-render]').click();
  await page.locator('[data-output]').waitFor();
  const bandBytes = await download('[data-midi]');
  assert.deepEqual(await download('#rhythm-mrt2-midi'), hitsBytes);
  assert.equal(new Midi(bandBytes).tracks.filter(track => track.notes.length).length, 3);
  assert.equal((await download('[data-wav]')).subarray(0, 4).toString(), 'RIFF');
  await page.locator('#undo-hit').click();
  assert(await page.locator('[data-output]').isHidden(), 'undo invalidates generated music');
  assert.deepEqual(await download('#rhythm-mrt2-midi'), before);
  await page.locator('#file').setInputFiles(path.join(root, 'web/rhythm-example.wav'));
  await page.locator('#result').waitFor({state: 'hidden'});
  await page.locator('#analyze').click();
  await page.locator('#result').waitFor();
  assert(await page.locator('[data-output]').isHidden(), 'replacing the recording clears the arrangement');

  await page.goto(base + '/optimized/dist/');
  await page.locator('#model-badge.ready').waitFor({timeout: 90000});
  await page.locator('#example').click();
  await page.locator('#convert').click();
  await page.locator('#result-content').waitFor({timeout: 90000});
  for (const timbre of ['soft', 'bright']) {
    await page.locator('#timbre').selectOption(timbre);
    await page.locator('#confirm-melody').click();
    const melody = await input('#humming-mrt2-export', 'humming');
    assert.deepEqual(Buffer.from(melody.midi_base64, 'base64'), await download('#download-midi'));
    assert(melody.duration_s > 0);
  }

  await page.goto(base + '/text-creation.html');
  const prompt = page.locator('#creation-prompt');
  await prompt.fill('  \n ');
  assert(await page.locator('#text-mrt2-export').isDisabled());
  const original = '  温暖的 lo-fi\n鼓点稀疏。  ';
  await prompt.fill(original);
  const text = await input('#text-mrt2-export', 'text');
  assert.deepEqual(text, {schema_version: 1, source: 'text', prompt: original, midi_base64: null, duration_s: null});
  await prompt.fill('来一段，慢一点');
  await page.locator('#text-generate').click();
  await page.locator('#text-output').waitFor();
  assert.equal((await download('#text-wav')).subarray(0, 4).toString(), 'RIFF');
  assert.deepEqual(errors, []);
  console.log('MRT2 handoff: edited rhythm MIDI, humming MIDI bytes, raw text, and generation passed.');
} finally {
  await browser.close();
}
