import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const event=JSON.parse(await readFile(new URL('../examples/web_band/humming.agent.json',import.meta.url)));
const base=process.env.INPUT_LAB_URL||'http://127.0.0.1:4186';
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage();
try{
  await page.goto(base+'/session.html');
  await page.waitForFunction(()=>document.querySelector('#session-state').dataset.ready==='true');
  // Use the same window/origin boundary as the real input page, with a validated fixture.
  const frame=page.frame({url:/optimized\/dist/});
  await frame.evaluate(event=>parent.postMessage({type:'jammate-input',event},location.origin),event);
  await page.waitForFunction(()=>document.querySelector('#humming-summary').dataset.loaded==='true');
  let first;
  const url=base+'/api/session/render';
  await page.route(url,async route=>{const response=await route.fetch();first=await response.json();await route.abort('failed');},{times:1});
  await page.click('#render');await page.locator('#retry').waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('#retry').disabled);
  assert.equal(await page.locator('#outputs article').count(),0);
  const response=page.waitForResponse(url);await page.click('#retry');const retry=await(await response).json();
  assert.equal(retry.request_id,first.request_id);assert.equal(retry.state.state_version,first.state.state_version);
  await page.waitForFunction(id=>document.querySelector('#outputs article')?.dataset.request===id,retry.request_id);
  let release,arrived;const waiting=new Promise(r=>arrived=r),held=new Promise(r=>release=r);
  await page.route(url,async route=>{const response=await route.fetch();arrived();await held;await route.fulfill({response});},{times:1});
  await page.click('#render');await waiting;
  await page.selectOption('#key','7:major');release();
  await page.waitForFunction(()=>!document.querySelector('#render').disabled);
  assert.equal(await page.locator('#outputs article').count(),1,'late output not shown');
  assert.equal(await page.locator('#outputs article').getAttribute('data-old'),'true');
  assert.match(await page.locator('#outputs article').innerText(),/历史|旧版本/,'old result explicitly labelled');
  await page.setViewportSize({width:390,height:844});
  await page.locator('[data-tab="humming"]').click();
  await frame.locator('#example').click();await frame.locator('#convert').click();
  await frame.locator('[data-add-session]').waitFor({state:'visible',timeout:90000});
  await page.waitForFunction(()=>{const frame=document.querySelector('#humming-frame');return frame.contentDocument.documentElement.scrollHeight<=frame.clientHeight+2;});
  console.log('Session network retry, stale output and full mobile input visibility passed.');
} finally {await browser.close();}
