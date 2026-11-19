// Replay the local benchmark recording through the public page and inspect actual browser output.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import midiPackage from '@tonejs/midi';

const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '../../..');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || path.join(root, 'tmp/browser-deps/node_modules/playwright'));
const reference = path.resolve(process.argv[2] || path.join(root,'recordings/humming-tempo-20261119/fefb8cf3'));
const output = path.resolve(process.argv[3] || path.join(root,'tmp/humming-workbench-default',path.basename(reference)));
const recording = path.resolve(process.argv[4] || path.join(root,'../bench/jammate-fefb8cf3-original.webm'));
const python = process.env.PYTHON || (process.platform==='win32' ? path.join(root,'.venv/Scripts/python.exe') : 'python3');
const server = spawn(python, ['-u','-m','http.server','0','--bind','127.0.0.1','--directory','web'], {
  cwd:root, windowsHide:true
});
let browser;
try {
  const [ready] = await Promise.race([once(server.stdout,'data'), once(server,'exit').then(()=>{throw Error('Cannot start test server');})]);
  const port = /port (\d+)/.exec(ready.toString())[1];
  browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage({acceptDownloads:true,viewport:{width:1440,height:980},deviceScaleFactor:1});
  const errors = [];
  page.on('pageerror', e=>errors.push(e.message));
  await page.addInitScript(()=>{
    // Observe real draw calls and oscillator scheduling without substituting either implementation.
    const probe = window.humProbe = {bars:[],voices:[],attacks:[]};
    const ramp = AudioParam.prototype.linearRampToValueAtTime;
    AudioParam.prototype.linearRampToValueAtTime = function(level,time) {
      if (level > 0) probe.attacks.push(level);
      return ramp.call(this,level,time);
    };
    const canvas = CanvasRenderingContext2D.prototype;
    const clear = canvas.clearRect, rect = canvas.roundRect;
    canvas.clearRect = function(...args) {
      if (this.canvas.id==='piano-roll') probe.bars=[];
      return clear.apply(this,args);
    };
    canvas.roundRect = function(...args) {
      if (this.canvas.id==='piano-roll') probe.bars.push(args.slice(0,4));
      return rect.apply(this,args);
    };
    const connect = AudioNode.prototype.connect;
    AudioNode.prototype.connect = function(target,...args) {
      if (this instanceof GainNode && target===this.context.destination) {
        const tap=this.context.createMediaStreamDestination();
        connect.call(this,tap);
        const recorder=new MediaRecorder(tap.stream);
        const chunks=[];
        recorder.ondataavailable=e=>chunks.push(e.data);
        probe.audio=new Promise(resolve=>{recorder.onstop=async()=>{
          const blob=new Blob(chunks,{type:recorder.mimeType});
          const reader=new FileReader();
          reader.onload=()=>resolve(reader.result.split(',')[1]);
          reader.readAsDataURL(blob);
        };});
        probe.recorder=recorder;
        recorder.start();
      }
      return connect.call(this,target,...args);
    };
    const start=OscillatorNode.prototype.start, stop=OscillatorNode.prototype.stop;
    const scheduled=new WeakMap();
    OscillatorNode.prototype.start=function(time){
      const voice={frequency:this.frequency.value,time};
      scheduled.set(this,voice);probe.voices.push(voice);
      return start.call(this,time);
    };
    OscillatorNode.prototype.stop=function(time){
      if(scheduled.has(this)) scheduled.get(this).stop=time;
      return stop.call(this,time);
    };
  });
  await page.goto('http://127.0.0.1:'+port);
  await page.locator('a[href="optimized/dist/"]').click();
  await page.locator('#file').setInputFiles(recording);
  await page.locator('#convert').click({timeout:60000});
  await page.locator('#result-content').waitFor({state:'visible',timeout:120000});
  async function download(id) {
    const pending=page.waitForEvent('download');
    await page.locator(id).click();
    const file=await pending;
    return fs.readFile(await file.path());
  }
  const original=await download('#download-original');
  assert.deepEqual(original,await fs.readFile(recording));
  for (const id of ['download-event','download-midi','download-json'])
    assert.equal(await page.locator('#'+id).getAttribute('href'),null);
  assert(await page.locator('#band-panel').isHidden());
  await page.locator('#confirm-melody').click();
  const eventBytes=await download('#download-event'), midiBytes=await download('#download-midi');
  const melody=JSON.parse(eventBytes).payload.melody;
  const golden=JSON.parse(await fs.readFile(path.join(reference,'dynamics/strict.json'))).payload.melody;
  assert.equal(await page.locator('#revision').inputValue(),'current');
  assert.equal(melody.results.cleaned.policy.durationGate.experiment,'strict');
  assert.equal(melody.results.cleaned.policy.durationGate.normalMs,golden.results.cleaned.policy.durationGate.normalMs);
  assert.equal(melody.results.cleaned.policy.samePitchReattack,null);
  const musical = ns=>ns.map(n=>[n.pitchMidi,n.startSec,n.durationSec]);
  assert.deepEqual(musical(melody.notes),musical(golden.notes));
  assert.deepEqual(melody.notes,JSON.parse(await download('#download-json')).notes);
  const midi = new midiPackage.Midi(midiBytes), notes=midi.tracks.flatMap(t=>t.notes);
  assert.equal(notes.length,melody.notes.length);
  const referenceBytes=await fs.readFile(path.join(reference,'dynamics/strict.mid'));
  assert.deepEqual(midiBytes,referenceBytes);
  const archived = new midiPackage.Midi(referenceBytes);
  const noteTicks = m=>m.tracks.flatMap(t=>t.notes.map(n=>[n.midi,n.ticks,n.durationTicks]));
  assert.deepEqual(noteTicks(midi),noteTicks(archived));
  assert.equal(melody.playback.velocityPolicy,'basic_pitch_amplitude');
  assert(new Set(notes.map(n=>n.velocity)).size>1);
  const tick=melody.midiExport.timeRoundingToleranceSec;
  let maxStart=0,maxEnd=0;
  notes.forEach((n,i)=>{
    const e=melody.notes[i];
    assert.equal(n.midi,e.pitchMidi);assert.equal(n.velocity,e.velocity01);
    assert.equal(n.velocity,Math.max(1,Math.floor(e.modelActivation*127))/127);
    maxStart=Math.max(maxStart,Math.abs(n.time-e.startSec));
    maxEnd=Math.max(maxEnd,Math.abs(n.time+n.duration-e.startSec-e.durationSec));
  });
  assert(Math.max(maxStart,maxEnd)<=tick);
  await page.selectOption('#revision','previous');
  assert.deepEqual(await download('#download-event'),eventBytes);
  await page.locator('#confirm-melody').click();
  const previous=JSON.parse(await download('#download-event')).payload.melody;
  assert(previous.results.cleaned.policy.samePitchReattack);
  assert(!previous.results.cleaned.policy.durationGate);
  await page.selectOption('#revision','current');
  await page.locator('#confirm-melody').click();
  assert.deepEqual(await download('#download-midi'),referenceBytes);
  const graph=await page.locator('#piano-roll').evaluate(el=>({width:el.clientWidth,bars:window.humProbe.bars}));
  assert.equal(graph.bars.length,notes.length);
  const pitches=[...previous.notes,...melody.notes].map(n=>n.pitchMidi);
  const low=Math.min(...pitches)-2, high=Math.max(...pitches)+2;
  const xScale=(graph.width-8-38)/melody.source.durationSec, yScale=(205-28-13)/(high-low);
  notes.forEach((n,i)=>{
    const [x,y,w,h]=graph.bars[i];
    assert(Math.abs(x-(38+n.time*xScale))<.001 && Math.abs(w-Math.max(2,n.duration*xScale-1))<.001);
    assert(Math.abs(y+h/2-(205-28-(n.midi-low)*yScale))<.001);
  });
  await fs.mkdir(output,{recursive:true});
  await page.locator('#piano-roll').screenshot({path:path.join(output,'piano-roll.png')});
  await page.locator('#play-midi').click();
  await page.waitForFunction(()=>window.humProbe.voices.length>0);
  const {voices,attacks}=await page.evaluate(()=>({voices:window.humProbe.voices,attacks:window.humProbe.attacks}));
  assert.equal(voices.length,notes.length);
  assert.equal(attacks.length,notes.length);
  const origin=voices[0].time-notes[0].time;
  voices.forEach((v,i)=>{
    const n=notes[i];
    assert(Math.abs(attacks[i]-n.velocity*.7)<1e-6);
    assert(Math.abs(69+12*Math.log2(v.frequency/440)-n.midi)<.0001);
    assert(Math.abs(v.time-origin-n.time)<1e-6);
    assert(Math.abs(v.stop-v.time-.07-n.duration)<1e-6); // instrument release
  });
  await page.waitForFunction(()=>!document.querySelector('#play-midi').textContent.includes('停止'));
  const audio=await page.evaluate(async()=>{window.humProbe.recorder.stop();return window.humProbe.audio;});
  assert.deepEqual(errors,[]);
  const report={variant:'strict',durationSec:melody.source.durationSec,notes:notes.length,rollBars:graph.bars.length,
    auditionVoices:voices.length,maxMidiStartErrorMs:maxStart*1000,maxMidiEndErrorMs:maxEnd*1000,
    tickMs:tick*1000,frozenPitchAndTicksIdentical:true,
    velocityRange: [Math.min(...notes.map(n=>Math.round(n.velocity*127))),Math.max(...notes.map(n=>Math.round(n.velocity*127)))]};
  await Promise.all([
    fs.writeFile(path.join(output,'melody.mid'),midiBytes),fs.writeFile(path.join(output,'input-event.json'),eventBytes),
    fs.writeFile(path.join(output,'audition.webm'),Buffer.from(audio,'base64')),
    fs.writeFile(path.join(output,'verification.json'),JSON.stringify(report,null,2))
  ]);
  console.log(report);
  // Field recording with an actual C4 removed by the 110 ms gate.
  if (path.basename(reference)==='fefb8cf3') {
    const dropped=melody.results.cleaned.edits.find(edit=>edit.type==='drop_short_output' && edit.pitchMidi===60 && edit.durationSec>.100);
    assert(dropped);
    const start=dropped.startSec;
    const snapshot=await download('#download-event');
    await page.click('#add-note');
    await page.fill('#note-start',String(start));
    await page.fill('#note-end',(start+dropped.durationSec).toFixed(6));
    await page.selectOption('#note-pitch','60');
    await page.fill('#note-velocity','65');
    await page.click('#note-form [type=submit]');
    const manualId=await page.inputValue('#note-select');
    assert.equal(await page.locator('#note-select option').count(),notes.length+1);
    assert.deepEqual(await download('#download-event'),snapshot);
    assert.deepEqual(await download('#download-midi'),referenceBytes);
    // Select the short bar on the actual canvas, then change all four values.
    const [bar]=await page.evaluate(({start,xScale})=>window.humProbe.bars.filter(b=>Math.abs(b[0]-(38+start*xScale))<.15),{start,xScale});
    assert(bar);
    await page.locator('#piano-roll').click({position:{x:bar[0]+bar[2]/2,y:bar[1]+bar[3]/2}});
    assert.equal(await page.inputValue('#note-pitch'),'60');
    await page.fill('#note-start',(start+.003).toFixed(6));
    await page.fill('#note-end',(start+.093).toFixed(6));
    await page.selectOption('#note-pitch','64');
    await page.fill('#note-velocity','42');
    await page.click('#note-form [type=submit]');
    await page.click('#edit-note'); await page.click('#remove-note');
    assert.equal(await page.locator('#note-select option').count(),notes.length);
    await page.click('#undo-note');
    assert.equal(await page.locator('#note-select option').count(),notes.length+1);
    await page.evaluate(()=>{window.humProbe.voices=[];window.humProbe.attacks=[];});
    await page.click('#play-midi');
    await page.waitForFunction(()=>window.humProbe.voices.length>0);
    const heard=await page.evaluate(()=>({voices:window.humProbe.voices,attacks:window.humProbe.attacks}));
    assert.equal(heard.voices.length,notes.length+1);
    const idx=heard.voices.findIndex(v=>Math.abs(69+12*Math.log2(v.frequency/440)-64)<.001 &&
      Math.abs(v.time-heard.voices[0].time+notes[0].time-start-.003)<tick);
    assert(idx>=0);
    assert(Math.abs(heard.voices[idx].stop-heard.voices[idx].time-.07-.09)<=tick);
    assert(Math.abs(heard.attacks[idx]-.7*42/127)<1e-6);
    await page.waitForFunction(()=>!document.querySelector('#play-midi').textContent.includes('停止'));
    const editedAudio=await page.evaluate(async()=>{window.humProbe.recorder.stop();return window.humProbe.audio;});
    assert.deepEqual(await download('#download-event'),snapshot);
    await page.click('#confirm-melody');
    const editedEvent=await download('#download-event'), editedMidi=await download('#download-midi');
    const event=JSON.parse(editedEvent), reviewed=event.payload.melody;
    assert.equal(event.schema_version,'1.4.0'); assert.notEqual(event.event_id,JSON.parse(snapshot).event_id);
    assert.deepEqual(reviewed.results.raw,melody.results.raw);
    assert.deepEqual(reviewed.notes,JSON.parse(await download('#download-json')).notes);
    assert.deepEqual(reviewed.notes.filter(n=>n.id!==manualId),melody.notes);
    const recovered=reviewed.notes.find(n=>n.id===manualId);
    assert.equal(recovered.durationSec,.09);
    assert.equal(recovered.startSec,Number((start+.003).toFixed(6)));
    assert.equal(recovered.pitchMidi,64); assert.equal(recovered.velocity01,42/127);
    const parsed=new midiPackage.Midi(editedMidi).tracks.flatMap(t=>t.notes);
    assert.equal(parsed.length,reviewed.notes.length);
    parsed.forEach((n,i)=>{
      const e=reviewed.notes[i];
      assert.equal(n.midi,e.pitchMidi); assert.equal(n.velocity,e.velocity01);
      assert(Math.abs(n.time-e.startSec)<=tick && Math.abs(n.duration-e.durationSec)<=tick);
    });
    const count=await page.evaluate(()=>window.humProbe.bars.length);
    assert.equal(count,parsed.length);
    await fs.writeFile(path.join(output,'edited.input-event.json'),editedEvent);
    await fs.writeFile(path.join(output,'edited.mid'),editedMidi);
    await fs.writeFile(path.join(output,'edited-audition.webm'),Buffer.from(editedAudio,'base64'));
    await page.selectOption('#note-select',manualId);
    await page.locator('#piano-roll').screenshot({path:path.join(output,'edited-piano-roll.png')});
    await page.click('#edit-note'); await page.click('#remove-note');
    assert.deepEqual(await download('#download-midi'),editedMidi);
    await page.click('#confirm-melody');
    assert.deepEqual(await download('#download-midi'),referenceBytes);
    assert.equal(JSON.parse(await download('#download-event')).payload.melody.notes.length,notes.length);
    assert.deepEqual(errors,[]);
    console.log({manualNote:recovered, draftVoices:heard.voices.length, confirmedBars:count,
      unchangedUntilConfirmed:true, confirmedDeletion:true});
  }
} finally {
  await browser?.close();
  server.kill();
}
