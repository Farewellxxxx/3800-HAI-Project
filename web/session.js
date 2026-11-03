const $=id=>document.getElementById(id);
const frames=['rhythm','humming'].map(name=>$(name+'-frame'));
const pitchNames=['C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B'];
const keyName=key=>key?`${pitchNames[key.tonic]} ${key.mode==='major'?'大调':'小调'}`:'调性未定（旋律 + 鼓点）';
for(const mode of ['major','minor'])for(let tonic=0;tonic<12;tonic++){
  const option=document.createElement('option');option.value=`${tonic}:${mode}`;option.textContent=keyName({tonic,mode});$('key').append(option);
}
let session=null,revision=0,inputs={},busy=false,syncPromise=Promise.resolve(),synced=-1;
let candidate=null,retry=null,lastSuccessful=-1,version=0,epoch=0;
const outputs=[];
function resizeFrames(){
  for(const frame of frames){
    if(!frame.offsetParent||!frame.contentDocument?.body)continue;
    const height=frame.contentDocument.documentElement.offsetHeight+2;
    if(height>200&&height<12000&&frame.style.height!==`${height}px`)frame.style.height=`${height}px`;
  }
}
for(const frame of frames){
  const observe=()=>{new ResizeObserver(resizeFrames).observe(frame.contentDocument.body);resizeFrames();};
  frame.addEventListener('load',observe);
  if(frame.contentDocument?.readyState==='complete')observe();
}
window.addEventListener('resize',resizeFrames);
function status(text,error=false){$('status').textContent=text;$('status').dataset.error=error;}
function pauseFrames(except=null){for(const frame of frames)if(frame.contentWindow!==except)frame.contentWindow.postMessage({type:'jammate-pause'},location.origin);}
function pauseOutputs(except=null){for(const audio of $('outputs').querySelectorAll('audio'))if(audio!==except)audio.pause();}
function markHistorical(){for(const entry of outputs){entry.element.dataset.old='true';entry.element.querySelector('[data-result-state]').textContent='历史版本 · 请按该版本的设置试听';}}
function readDraft(){
  const tempoSource=$('tempo-source').value;
  if(tempoSource==='default')$('bpm').value='100';
  if(tempoSource==='rhythm'&&inputs.rhythm)$('bpm').value=inputs.rhythm.payload.rhythm.tempo_bpm;
  const key=$('key').value==='unknown'?null:{tonic:Number($('key').value.split(':')[0]),mode:$('key').value.split(':')[1]};
  return {inputs:structuredClone(inputs),settings:{tempo_source:tempoSource,bpm:Number($('bpm').value),key,
    melody_origin_s:Number($('melody-origin').value),placement_beats:Number($('placement').value),alignment_confirmed:$('alignment-confirmed').checked}};
}
function refresh(){
  const combined=!!(inputs.rhythm&&inputs.humming);
  $('bpm').disabled=$('tempo-source').value!=='manual';
  $('alignment-description').textContent=`哼唱录音 ${$('melody-origin').value||'0'} 秒处 → 会话第 ${$('placement').value||'0'} 拍。原始音符不对齐网格、不变速。`;
  const valid=$('settings').checkValidity()&&(!combined||$('alignment-confirmed').checked);
  $('render').disabled=!session||!Object.keys(inputs).length||!valid||busy;
  for(const button of document.querySelectorAll('[data-command],#send-command'))button.disabled=busy||lastSuccessful!==revision||synced!==revision||!session;
  for(const button of document.querySelectorAll('[data-command]'))if(button.dataset.command.includes('贝斯')&&$('key').value==='unknown')button.disabled=true;
  $('retry').hidden=!retry;$('retry').disabled=busy;
  for(const source of ['rhythm','humming']){
    const item=inputs[source],node=$(source+'-summary');node.dataset.loaded=!!item;
    node.textContent=!item?'尚未加入':source==='rhythm'?`${item.payload.rhythm.tempo_bpm.toFixed(1)} BPM · 拍点 ${item.payload.rhythm.onset_beats.join(' / ')}`:`${item.payload.melody.notes.length} 个音符 · ${item.payload.melody.selectedResult==='raw'?'原始识别':'连贯哼唱'}`;
    document.querySelector(`[data-remove="${source}"]`).disabled=!item;
  }
  $('key-help').textContent=$('key').value==='unknown'?'调性未确定：贝斯与和弦暂停，保留旋律和鼓点。选择调性后启用两者。':'使用所选调性的规则和声；不会自动改写旋律，也不保证每个旋律音都与每个和弦吻合。';
}
async function api(path,data){
  const response=await fetch('/api/session/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'请求失败，请重试。');
  return result;
}
function changed(){
  revision++;synced=-1;retry=null;candidate=null;$('apply-key').disabled=true;
  pauseOutputs();markHistorical();
  status('素材或设置已更新，请生成当前版本。正在返回的旧结果不会覆盖它。');
  const sid=session,rev=revision,data=readDraft();refresh();
  $('draft-status').textContent='正在检查当前设置…';$('draft-status').dataset.error=false;
  syncPromise=(async()=>{
    if(!sid)return false;
    try{
      const result=await api('draft',{session_id:sid,revision:rev,draft:data});
      if(sid!==session||rev!==revision)return false;
      synced=rev;candidate=result.key_suggestion;
      $('key-suggestion').textContent=candidate?`调性候选：${keyName(candidate.key)}${candidate.ambiguous?'（证据不足或存在歧义）':''}。这是启发式建议，需你确认；不会自动采用。`:'当前没有足够证据给出调性候选，可以手动选择或先用旋律 + 鼓点。';
      $('apply-key').disabled=!candidate;
      $('draft-status').textContent='设置已检查，生成时会按以上方式处理。';
      refresh();return true;
    }catch(error){if(sid===session&&rev===revision){$('draft-status').textContent=error.message;$('draft-status').dataset.error=true;refresh();}return false;}
  })();
}
function media(encoded,type){return URL.createObjectURL(new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],{type}));}
function showResult(result){
  pauseOutputs();pauseFrames();version++;
  markHistorical();
  const element=document.createElement('article');element.dataset.request=result.request_id;element.dataset.old='false';
  const title=document.createElement('h3');title.textContent=`版本 ${version} · ${result.text||'按当前素材生成'}`;
  const info=document.createElement('p');info.className='muted';
  const source={manual:'手动',rhythm:'节拍输入',default:'默认'}[result.settings.tempo_source];
  info.textContent=`${result.tempo_bpm.toFixed(1)} BPM（${source}） · ${keyName(result.settings.key)} · ${result.bars} 小节 · ${result.renderer}`;
  const audio=document.createElement('audio');audio.controls=true;audio.setAttribute('aria-label',`版本 ${version} 伴奏`);
  const urls=[media(result.wav,'audio/wav'),media(result.midi,'audio/midi')];audio.src=urls[0];
  const {wav,midi,...receipt}=result;urls.push(URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'})));
  const links=document.createElement('div');links.className='downloads';
  ['WAV','MIDI','记录 JSON'].forEach((name,i)=>{const link=document.createElement('a');link.textContent=`下载 ${name}`;link.href=urls[i];link.download=`jammate-v${version}.${['wav','mid','json'][i]}`;links.append(link);});
  audio.addEventListener('play',()=>{pauseOutputs(audio);pauseFrames();});
  const badge=document.createElement('p');badge.dataset.resultState='';badge.className='muted';badge.textContent='当前版本';
  element.append(badge,title,info,audio,links);$('outputs').prepend(element);outputs.unshift({element,urls});
  while(outputs.length>2){const entry=outputs.pop();entry.element.querySelector('audio').pause();entry.element.remove();entry.urls.forEach(URL.revokeObjectURL);}
  const names={drums:'鼓',bass:'贝斯',keys:'键盘',lead:'旋律'};
  $('layers').textContent=result.state.arrangement.layers.map(l=>`${names[l.name]}：${l.active?'开启':'关闭'}，力度 ${Math.round(l.level*100)}%，密度 ${Math.round(l.density*100)}%`).join(' · ');
}
async function generate(text='',repeating=false){
  if(busy||!session)return;
  if(!$('settings').reportValidity())return;
  if(!repeating&&!await syncPromise)return;
  if(synced!==revision)return;
  const sid=session,rev=revision,token=epoch;
  const request=repeating?retry:{session_id:sid,revision:rev,request_id:crypto.randomUUID(),text};
  if(!request)return;
  busy=true;retry=request;refresh();status('乐队正在编排和渲染…');pauseOutputs();pauseFrames();
  try{
    const result=await api('render',request);
    if(sid!==session||rev!==revision||token!==epoch)return;
    showResult(result);lastSuccessful=rev;retry=null;status('当前版本已生成。可以试听、调整或与上一版比较。');
  }catch(error){if(sid===session&&rev===revision&&token===epoch)status(`本次未显示新结果：${error.message}`,true);}
  finally{if(token===epoch){busy=false;refresh();}}
}
async function newSession(){
  const token=++epoch,old=session;session=null;busy=false;retry=null;inputs={};revision=0;synced=-1;lastSuccessful=-1;version=0;
  pauseOutputs();pauseFrames();for(const entry of outputs.splice(0)){entry.element.remove();entry.urls.forEach(URL.revokeObjectURL);}
  $('settings').reset();$('text-command').value='';$('layers').textContent='';$('session-state').dataset.ready='false';refresh();
  $('session-state').textContent='正在创建会话…';
  try{
    if(old)await api('close',{session_id:old});
    const created=await api('create',{});
    if(token!==epoch){await api('close',{session_id:created.session_id});return;}
    session=created.session_id;$('session-state').dataset.session=session;$('session-state').dataset.ready='true';
    $('session-state').textContent='会话已就绪 · 本地规则指挥 · 原录音仍保留在输入页';status('加入素材后开始生成。');changed();
  }catch(error){$('session-state').textContent=error.message;status('创建失败，请点击“新建会话”重试。',true);}
}
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||!frames.some(f=>f.contentWindow===event.source))return;
  if(event.data?.type==='jammate-play'){pauseOutputs();pauseFrames(event.source);return;}
  if(event.data?.type!=='jammate-input'||!session)return;
  const input=event.data.event,source=input?.source;
  if(!['humming','rhythm'].includes(source))return;
  inputs[source]=structuredClone(input);$('alignment-confirmed').checked=false;changed();
  status(`已加入${source==='humming'?'哼唱':'节拍'}。请确认下方音乐设置。`);
});
for(const button of document.querySelectorAll('[data-tab]'))button.onclick=()=>{
  pauseFrames();pauseOutputs();
  for(const name of ['rhythm','humming'])$(name+'-pane').hidden=name!==button.dataset.tab;
  for(const tab of document.querySelectorAll('[data-tab]'))tab.setAttribute('aria-pressed',String(tab===button));
  requestAnimationFrame(resizeFrames);
};
for(const button of document.querySelectorAll('[data-remove]'))button.onclick=()=>{delete inputs[button.dataset.remove];if(!inputs.rhythm&&$('tempo-source').value==='rhythm')$('tempo-source').value='default';changed();};
for(const control of $('settings').querySelectorAll('input,select'))control.addEventListener('input',()=>{if(['melody-origin','placement','bpm','tempo-source'].includes(control.id))$('alignment-confirmed').checked=false;changed();});
$('settings').onsubmit=event=>event.preventDefault();
$('apply-key').onclick=()=>{if(candidate){$('key').value=`${candidate.key.tonic}:${candidate.key.mode}`;changed();}};
$('render').onclick=()=>generate();$('retry').onclick=()=>generate('',true);
for(const button of document.querySelectorAll('[data-command]'))button.onclick=()=>generate(button.dataset.command);
$('send-command').onclick=()=>{if($('text-command').value.trim())generate($('text-command').value);};
$('new-session').onclick=newSession;
window.addEventListener('pagehide',event=>{pauseOutputs();pauseFrames();if(!event.persisted&&session)navigator.sendBeacon('/api/session/close',new Blob([JSON.stringify({session_id:session})],{type:'application/json'}));});
newSession();
