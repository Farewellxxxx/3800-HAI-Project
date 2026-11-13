// Real browser + actual local APIs. MRT2_REAL=1 opts into real model inference.
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const base=process.env.INPUT_LAB_URL||'http://127.0.0.1:4196';
const real=process.env.MRT2_REAL==='1';
const out=path.resolve(process.env.INPUT_MRT2_OUT||`tmp/input-mrt2-${real?'real':'precise'}`);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1280,height:950},acceptDownloads:true});
page.setDefaultTimeout(15000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const report={mode:real?'real_magenta_rt':'real_numpy_synthesis',url:base,cases:[]};
async function artifact(kind,result){
 const {wav,midi,...trace}=result;
 await writeFile(path.join(out,kind+'.wav'),Buffer.from(wav,'base64'));
 await writeFile(path.join(out,kind+'.mid'),Buffer.from(midi,'base64'));
 await writeFile(path.join(out,kind+'.trace.json'),JSON.stringify(trace,null,2));
 await writeFile(path.join(out,kind+'.input-event.json'),JSON.stringify(result.input_event,null,2));
 assert.deepEqual(result.plan.trigger_event_ids,[result.input_event.event_id]);
 assert.equal(result.plan.based_on_state_version,result.state_before.state_version);
 if(real){
   assert.equal(result.receipt.inference,'real_magenta_rt');
   assert.equal(result.receipt.phase,'preview');assert.equal(result.receipt.state_committed,false);
   assert.deepEqual(result.state_after,result.state_before);
 }
 const selector=kind==='text'?'#text-audio':'[data-output] audio';
 await page.waitForFunction(s=>document.querySelector(s)?.src?.startsWith('blob:'),selector);
 const decoded=await page.locator(selector).evaluate(async player=>{
   const context=new AudioContext();
   try{
     const audio=await context.decodeAudioData(await(await fetch(player.src)).arrayBuffer());
     const samples=audio.getChannelData(0);
     await player.play();
     for(let i=0;i<12 && player.currentTime===0;i++)await new Promise(resolve=>setTimeout(resolve,250));
     const advanced=player.currentTime>0, playing=!player.paused, readyState=player.readyState;
     player.pause();
     return {duration:audio.duration,channels:audio.numberOfChannels,sampleRate:audio.sampleRate,
       rms:Math.sqrt(samples.reduce((s,x)=>s+x*x,0)/samples.length),playbackAdvanced:advanced,playing,readyState};
   }finally{await context.close();}
 });
 assert(decoded.rms>.0001);assert(decoded.playing && decoded.readyState>=3,JSON.stringify(decoded));
 assert(decoded.playbackAdvanced,'browser playback clock must advance');
 if(real)assert.equal(decoded.channels,2);
 await page.screenshot({path:path.join(out,kind+'.png'),fullPage:true});
 report.cases.push({kind,event_id:result.input_event.event_id,plan_id:result.plan.plan_id,
   renderer:result.renderer,receipt:result.receipt,timing_s:result.timing_s,decoded});
}
try{
 await page.goto(base+'/text-creation.html');
 await page.locator('#provider-state').filter({hasText:/配置|本地规则/}).waitFor();
 if(real){await page.locator('summary').click();await page.selectOption('#text-renderer','mrt2');await page.check('#text-preview');}
 const raw='  来一段，慢一点\n';
 await page.fill('#creation-prompt',raw);
 let response=page.waitForResponse(r=>r.url().endsWith('/text/turn'),{timeout:600000});
 await page.click('#text-generate');
 let reply=await response, result=await reply.json();
 assert.equal(reply.status(),200,result.error);
 assert.equal(reply.request().postDataJSON().text,raw,'submitted text must retain exact whitespace');
 assert.equal(result.input_event.payload.text,raw);
 assert.equal(result.input_event.source,'text');assert.equal(result.input_event.confidence,null);
 const textDownload=await page.locator('#text-event').evaluate(async a=>(await fetch(a.href)).json());
 assert.deepEqual(textDownload,result.input_event,'downloaded text event must match the accepted event');
 await artifact('text',result);

 for(const kind of ['rhythm','humming']){
   await page.goto(base+(kind==='rhythm'?'/rhythm.html':'/optimized/dist/'));
   await page.click('#example');
   if(kind==='rhythm')await page.click('#analyze');
   else {await page.waitForFunction(()=>!document.querySelector('#convert').disabled);await page.click('#convert');}
   await page.locator('[data-render]').waitFor({state:'visible',timeout:120000});
   if(real){await page.selectOption('[data-backend]','mrt2');await page.check('[data-preview]');}
   response=page.waitForResponse(r=>r.url().endsWith('/input/render'),{timeout:600000});
   await page.click('[data-render]');
   reply=await response;result=await reply.json();
   assert.equal(reply.status(),200,result.error);
   assert.deepEqual(reply.request().postDataJSON().event,result.input_event);
   const downloaded=await page.locator('[data-event]').evaluate(async a=>(await fetch(a.href)).json());
   assert.deepEqual(downloaded,result.input_event);
   if(kind==='humming'){
     const exported=await page.locator('#download-event').evaluate(async a=>(await fetch(a.href)).json());
     assert.deepEqual(exported,result.input_event);
     assert.deepEqual(result.input_event.payload.melody.notes.map(n=>n.pitchMidi),[60,64,67,64,62]);
   }else assert.deepEqual(result.input_event.payload.rhythm.onset_beats,[0,1,1.5,3]);
   await artifact(kind,result);
   await page.selectOption('[data-backend]',real?'default':'mrt2');
   assert.equal(await page.locator('[data-output]').isVisible(),false,'changing backend invalidates prior audio');
 }
 assert.deepEqual(errors,[]);
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await writeFile(path.join(out,'report.json'),JSON.stringify(report,null,2));
 console.log(`Passed ${report.cases.length} inputs: ${report.mode}; artifacts ${out}`);
}finally{await browser.close();}
