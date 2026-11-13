// One render belongs to the selected input. Discard late responses after a new take.
export function attachBandPanel(panel, {endpoint = '/api/create', payload = event => event, onResult, backends = false} = {}) {
  panel.innerHTML = `<h3>听创作结果</h3>
    <p>从这次输入发展出一段新音乐，生成后可以试听或下载。</p>
    ${backends ? `<label>生成后端 <select data-backend><option value="default">精确编排（当前音源）</option><option value="mrt2">MRT2 生成试听</option></select></label>
    <label><input type="checkbox" data-preview disabled>允许生成试听：MRT2 的音符与声部保留尚未验证，试听不提交音乐状态。</label>` : ''}
    <button type="button" data-render>生成音乐</button>
    <a data-event download="band-input.json">下载创作输入 JSON</a>
    <p role="status" data-status></p>
    <div data-output hidden><audio controls aria-label="创作结果"></audio>
      <p><a data-wav download="band.wav">下载 WAV</a> ·
      <a data-midi download="band.mid">下载 MIDI</a> ·
      <a data-trace download="band-trace.json">下载生成记录</a></p></div>`;
  const find = selector => panel.querySelector(selector);
  const button = find('[data-render]'), audio = find('audio');
  const original = document.getElementById('original');
  if (original) {
    audio.addEventListener('play', () => original.pause());
    original.addEventListener('play', () => audio.pause());
  }
  let current, pending;
  const urls = [];

  function url(blob) {
    const value = URL.createObjectURL(blob);
    urls.push(value);
    return value;
  }
  function media(encoded, type) {
    const bytes = Uint8Array.from(atob(encoded), ch => ch.charCodeAt(0));
    return url(new Blob([bytes], {type}));
  }
  function select(event) {
    pending?.abort();
    pending = null;
    current = event;
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    for (const link of panel.querySelectorAll('a')) link.removeAttribute('href');
    for (const old of urls.splice(0)) URL.revokeObjectURL(old);
    find('[data-output]').hidden = true;
    find('[data-status]').textContent = '';
    panel.hidden = !event;
    button.disabled = !event;
    if (event) find('[data-event]').href = url(new Blob([JSON.stringify(event, null, 2)], {type:'application/json'}));
    onResult?.(null);
  }
  button.onclick = async () => {
    const event = current;
    if (!event || button.disabled) return;
    select(event);
    const request = new AbortController();
    pending = request;
    button.disabled = true;
    find('[data-status]').textContent = '乐队正在编排和渲染…';
    try {
      const body = backends ? {...payload(event), renderer:find('[data-backend]').value,
        allow_preview:find('[data-preview]').checked} : payload(event);
      const response = await fetch(endpoint, {method:'POST', signal:request.signal,
        headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const result = await response.json();
      if (request !== pending) return;
      if (!response.ok) throw new Error(result.error);
      const wav = media(result.wav, 'audio/wav');
      audio.src = wav;
      find('[data-wav]').href = wav;
      find('[data-midi]').href = media(result.midi, 'audio/midi');
      const {wav:ignoredWav,midi:ignoredMidi,...trace} = result;
      find('[data-trace]').href = url(new Blob([JSON.stringify(trace,null,2)],{type:'application/json'}));
      const preview = result.receipt?.phase === 'preview';
      find('[data-midi]').textContent = preview ? '下载条件 MIDI（非音频转写）' : '下载 MIDI';
      find('[data-output]').hidden = false;
      const agentLabel = result.agent === 'rule' ? ' · 本地规则 Agent' : '';
      find('[data-status]').textContent = `${result.bars} 小节 · ${result.tempo_bpm.toFixed(1)} BPM${agentLabel} · ${result.renderer}`;
      if (preview) find('[data-status]').textContent += ' · 仅生成试听，音乐状态未提交。';
      if (result.warnings?.length || result.manager_diagnostics?.last_log_error)
        find('[data-status]').textContent += ' · 部分诊断记录未能保存';
      onResult?.(result);
    } catch (error) {
      if (request === pending) {
        find('[data-status]').textContent = `生成失败：${error.message}`;
        button.disabled = false;
      }
    } finally {
      if (request === pending) pending = null;
    }
  };
  if (backends) {
    for (const field of [find('[data-backend]'),find('[data-preview]')]) field.onchange = () => {
      find('[data-preview]').disabled = find('[data-backend]').value !== 'mrt2';
      if (find('[data-preview]').disabled) find('[data-preview]').checked = false;
      select(current);
    };
  }
  window.addEventListener('pagehide', event => {
    if (pending) {
      pending.abort();
      pending = null;
      button.disabled = !current;
      find('[data-status]').textContent = '';
    }
    audio.pause();
    if (!event.persisted) select(null);
  });
  select(null);
  return select;
}
