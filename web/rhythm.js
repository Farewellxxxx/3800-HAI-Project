import {attachBandPanel} from './band-panel.js';
import {downloadMrt2Input, downloadMrt2Midi, prepareMrt2Input} from './mrt2-input.js';

const $=id=>document.getElementById(id);
const mrt2Source = $('rhythm-mrt2-source');
const mrt2Status = $('rhythm-mrt2-status');
let buffer, sourceURL, recorder, stream, timer, phase='idle', startedAt=0, disposed=false;
let sessionId, captureEpoch=0, operation=0;
let selectedRhythm = null;
let arrangement = null;
let mrt2Request = null;
const selectBandInput = attachBandPanel($('band-panel'), {
  endpoint: '/api/reference/input/render', backends: true,
  payload: event => ({
    event, mode: $('rhythm-mode').value, energy: Number($('rhythm-energy').value), bars: Number($('rhythm-bars').value)
  }),
  onResult: result => {
    arrangement = result;
    if (mrt2Source.value === 'arrangement') {
      cancelMrt2Export();
      syncMrt2Input();
    }
  }
});

function syncMrt2Input() {
  const useArrangement = mrt2Source.value === 'arrangement';
  const ready = selectedRhythm?.payload.status === 'ready' && (!useArrangement || arrangement);
  $('rhythm-mrt2-midi').disabled = $('rhythm-mrt2-export').disabled = !ready || phase !== 'idle' || Boolean(mrt2Request);
  if (useArrangement && selectedRhythm && !arrangement)
    mrt2Status.textContent = '请先用上方的「生成音乐」编好伴奏。';
}

function cancelMrt2Export() {
  mrt2Request?.abort();
  mrt2Request = null;
  mrt2Status.textContent = '';
}

async function exportMrt2(save) {
  const event = selectedRhythm;
  if (phase !== 'idle' || event?.payload.status !== 'ready' || mrt2Request) return;
  const useArrangement = mrt2Source.value === 'arrangement';
  if (useArrangement && !arrangement) return;
  const request = new AbortController();
  mrt2Request = request;
  mrt2Status.textContent = '正在准备所选 MIDI…';
  syncMrt2Input();
  try {
    let midi, duration;
    if (useArrangement) {
      midi = arrangement.midi;
      duration = arrangement.bars * 4 * 60 / arrangement.tempo_bpm;
    } else {
      const response = await fetch('/api/reference/rhythm/midi', {
        method: 'POST', signal: request.signal,
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({event})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      midi = result.midi;
      duration = result.duration_s;
    }
    if (mrt2Request !== request) return;
    save(prepareMrt2Input(useArrangement ? 'rhythm_arrangement' : 'rhythm_hits', {midi, duration}));
    mrt2Status.textContent = '已导出所选输入。';
  } catch (error) {
    if (mrt2Request === request) mrt2Status.textContent = `导出失败：${error.message}`;
  } finally {
    if (mrt2Request === request) {
      mrt2Request = null;
      syncMrt2Input();
    }
  }
}

mrt2Source.onchange = () => {
  cancelMrt2Export();
  syncMrt2Input();
};
$('rhythm-mrt2-midi').onclick = () => exportMrt2(downloadMrt2Midi);
$('rhythm-mrt2-export').onclick = () => exportMrt2(downloadMrt2Input);

function sync(){
  for(const id of ['file','example','count','tempo','origin'])$(id).disabled=phase!=='idle';
  $('tempo').disabled=phase!=='idle'||$('count').value!=='0';
  $('record').disabled=!['idle','recording'].includes(phase);
  $('record').textContent=phase==='recording'?'停止录音':'开始录音';
  $('analyze').disabled=phase!=='idle'||!buffer;
  syncMrt2Input();
}
function setPhase(value){phase=value;sync();}
function clearResult(){ selectedRhythm=null;cancelMrt2Export();selectBandInput(null);syncMrt2Input();$('result').hidden=true; }
function clearAudio(){
  clearResult();buffer=null;sessionId=null;$('original').pause();$('original').removeAttribute('src');$('original').load();
  if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=null;
  $('download-original').hidden=true;$('download-original').removeAttribute('href');
}
async function load(blob,token=operation){
  if(token!==operation)return;
  if(blob.size>15*1024*1024)throw Error('请使用 15 MB 以内的音频');
  let decoded;const ctx=new AudioContext();try{decoded=await ctx.decodeAudioData(await blob.arrayBuffer());}finally{await ctx.close();}
  if(token!==operation)return;buffer=decoded;
  if(buffer.duration<.5||buffer.duration>30){buffer=null;throw Error('录音需为 0.5–30 秒');}
  if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=URL.createObjectURL(blob);$('original').src=sourceURL;
  $('download-original').href=sourceURL;
  $('download-original').download=blob instanceof File ? blob.name : `rhythm-original.${blob.type.includes('wav')?'wav':blob.type.includes('mp4')?'m4a':blob.type.includes('ogg')?'ogg':'webm'}`;
  $('download-original').hidden=false;
  sessionId=crypto.randomUUID();startedAt=0; $('status').textContent=`已载入 ${buffer.duration.toFixed(1)} 秒录音。`;sync();
}
function reportError(error){$('status').textContent=error.name==='NotAllowedError'?'麦克风权限未开启，可以允许权限或导入录音。':error.name==='EncodingError'?'无法解码这段音频，请使用有效的 WAV、MP3 或 WebM 文件。':error.message;}
async function replaceAudio(getBlob){
  if(phase!=='idle')return;
  const token=++operation;setPhase('loading');clearAudio();
  try{await load(await getBlob(),token);}catch(e){if(token===operation){clearAudio();reportError(e);}}finally{if(token===operation)setPhase('idle');}
}
function releaseMicrophone(){clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());stream=null;}
function stopRecording(){if(phase!=='recording'||recorder?.state!=='recording')return;setPhase('stopping');recorder.stop();}
function wavBase64(audio){
  const n=audio.length, data=new ArrayBuffer(44+n*2),v=new DataView(data);
  const text=(at,s)=>[...s].forEach((c,i)=>v.setUint8(at+i,c.charCodeAt(0)));
  text(0,'RIFF');v.setUint32(4,36+n*2,true);text(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,audio.sampleRate,true);v.setUint32(28,audio.sampleRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,n*2,true);
  for(let i=0;i<n;i++){let s=0;for(let c=0;c<audio.numberOfChannels;c++)s+=audio.getChannelData(c)[i]/audio.numberOfChannels;v.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,s))*32767),true);}
  const bytes=new Uint8Array(data);let textData='';for(let i=0;i<bytes.length;i+=8192)textData+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(textData);
}
$('file').onchange = () => {
  const file = $('file').files[0];
  $('file').value = '';
  if (file) replaceAudio(() => file);
};
$('example').onclick=()=>replaceAudio(async()=>{const r=await fetch('rhythm-example.wav');if(!r.ok)throw Error('示例未找到，请先生成示例音频。');return r.blob();});
$('record').onclick=async()=>{
  if(phase==='recording'){stopRecording();return;}
  if(phase!=='idle')return;
  setPhase('requesting');clearResult();
  const epoch=captureEpoch;
  try{
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw Error('浏览器无法录音，请在本机 Chrome／Edge 中打开，或导入音频。');
    const acquired=await navigator.mediaDevices.getUserMedia({audio:true});
    if(disposed||epoch!==captureEpoch){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;
    const capture=new MediaRecorder(stream),chunks=[];let failed=false;recorder=capture;
    capture.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    capture.onerror=()=>{if(recorder!==capture||disposed)return;failed=true;releaseMicrophone();recorder=null;setPhase('idle');$('status').textContent='录音中断，请重新录制或导入。';};
    capture.onstop=async()=>{
      if(failed||disposed||recorder!==capture)return;
      releaseMicrophone();recorder=null;
      const token=++operation;setPhase('loading');
      try{await load(new Blob(chunks,{type:capture.mimeType}),token);}catch(e){if(token===operation){clearAudio();reportError(e);}}finally{if(token===operation)setPhase('idle');}
    };
    operation++;clearAudio();capture.start();setPhase('recording');timer=setTimeout(stopRecording,20000);
    $('status').textContent=$('count').value==='0'?'正在录音：按指定 BPM 拍一小节。':'正在录音：四下均匀定速，接着一小节。';
  }catch(e){if(epoch!==captureEpoch)return;releaseMicrophone();recorder=null;reportError(e);setPhase('idle');}
};
for(const id of ['count','tempo','origin'])$(id).onchange=()=>{clearResult();sync();};
for (const id of ['rhythm-mode', 'rhythm-energy', 'rhythm-bars']) {
  $(id).onchange = () => selectBandInput(selectedRhythm);
}
$('analyze').onclick=async()=>{
  if(phase!=='idle'||!buffer)return;
  for(const field of [$('tempo'),$('origin')]){
    if(!field.disabled&&!field.checkValidity()){
      field.closest('details').open=true;
      field.reportValidity();
      return;
    }
  }
  const token=++operation;setPhase('analyzing');clearResult();$('status').textContent='正在本机分析，首次调用可能需要稍等…';
  try{const r=await fetch('/api/reference/rhythm/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({wav:wavBase64(buffer),session_id:sessionId,started_at:startedAt,count_in:Number($('count').value),tempo:Number($('tempo').value),origin:$('origin').value===''?null:Number($('origin').value)})});
    const event=await r.json();if(token!==operation)return;if(!r.ok)throw Error(event.error);const rhythm=event.payload.rhythm;selectedRhythm=event;selectBandInput(event);
    $('event').textContent=JSON.stringify(event,null,2);$('summary').textContent=`${rhythm.tempo_bpm.toFixed(1)} BPM · 拍点 [${rhythm.onset_beats.join(', ')}] · 网格贴合度 ${rhythm.confidence.toFixed(2)}`;
    $('result').hidden=false;$('status').textContent='已识别节拍。你可以选择编排方式，再生成音乐。';
  }catch(e){if(token===operation)$('status').textContent=`分析失败：${e.message}`;}finally{if(token===operation)setPhase('idle');}
};
window.addEventListener('pagehide',event=>{disposed=true;captureEpoch++;operation++;cancelMrt2Export();recorder=null;releaseMicrophone();$('original').pause();if(!event.persisted&&sourceURL)URL.revokeObjectURL(sourceURL);setPhase('idle');});
window.addEventListener('pageshow',()=>{disposed=false;sync();});
sync();
