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
  const source = page.locator('#rhythm-mrt2-source');
  const exportButton = page.locator('#rhythm-mrt2-export');
  await source.selectOption('arrangement');
  assert(await exportButton.isDisabled(), 'the arrangement requires a rendered clip');
  await source.selectOption('hits');
  const hits = await input('#rhythm-mrt2-export', 'rhythm_hits');
  const hitsBytes = Buffer.from(hits.midi_base64, 'base64');
  assert.deepEqual(await download('#rhythm-mrt2-midi'), hitsBytes);
  const hitsMidi = new Midi(hitsBytes);
  const tracks = hitsMidi.tracks.filter(track => track.notes.length);
  assert.equal(tracks.length, 1);
  assert.equal(tracks[0].channel, 9);
  assert.deepEqual(tracks[0].notes.map(note => note.ticks / hitsMidi.header.ppq), [0, 1, 1.5, 3]);

  await source.selectOption('arrangement');
  await page.locator('#rhythm-mode').selectOption('follow');
  await page.locator('[data-render]').click();
  await page.locator('[data-output]').waitFor();
  const band = await input('#rhythm-mrt2-export', 'rhythm_arrangement');
  const bandBytes = Buffer.from(band.midi_base64, 'base64');
  assert.deepEqual(bandBytes, await download('[data-midi]'));
  assert.deepEqual(bandBytes, await download('#rhythm-mrt2-midi'));
  assert.equal(new Midi(bandBytes).tracks.filter(track => track.notes.length).length, 3);
  assert.equal((await download('[data-wav]')).subarray(0, 4).toString(), 'RIFF');
  await page.locator('#rhythm-mode').selectOption('simplify');
  assert(await exportButton.isDisabled(), 'a change in arrangement settings invalidates the earlier MIDI');
  await source.selectOption('hits');
  assert.deepEqual(await download('#rhythm-mrt2-midi'), hitsBytes, 'the hit track is independent of arrangement settings');
  await source.selectOption('arrangement');
  await page.locator('[data-render]').click();
  await page.locator('[data-output]').waitFor();
  await page.locator('#file').setInputFiles(path.join(root, 'web/rhythm-example.wav'));
  await page.locator('#result').waitFor({state: 'hidden'});
  await page.locator('#analyze').click();
  await page.locator('#result').waitFor();
  assert(await exportButton.isDisabled(), 'replacing the recording clears the arrangement');

  await page.goto(base + '/optimized/dist/');
  await page.locator('#model-badge.ready').waitFor({timeout: 90000});
  await page.locator('#example').click();
  await page.locator('#convert').click();
  await page.locator('#result-content').waitFor({timeout: 90000});
  for (const variant of ['cleaned', 'raw']) {
    await page.locator('#variant').selectOption(variant);
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
  console.log('MRT2 handoff: rhythm MIDI selection, humming MIDI bytes, raw text, and original generation passed.');
} finally {
  await browser.close();
}
